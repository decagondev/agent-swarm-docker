"""SwarmManager — create / wait / cleanup short-lived Docker Swarm services.

The manager talks to a `_DockerClientProtocol`-shaped object so the real
`docker.DockerClient` and a `FakeDockerClient` test double are
interchangeable. The actual `docker.from_env()` resolution happens lazily in
`__init__` only if no client is injected.

Label convention (used for filtering, cleanup, observability):
    agent-swarm.job-id      — the supervisor's job correlation id
    agent-swarm.agent       — the registered agent name
    agent-swarm.role        — 'ephemeral' (one-shot run-to-completion)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from core.logging import SwarmEventLogger
from core.swarm.service_spec import ServiceSpec

# Env vars that need to flow from the supervisor container down into every
# spawned agent service so LLM-aware agents can talk to the provider.
# Anything that isn't set in the supervisor's environment is simply skipped.
PROPAGATED_ENV_VARS = (
    "LLM_PROVIDER",
    "LLM_MODEL",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "XAI_API_KEY",
)


class SwarmServiceError(RuntimeError):
    """A spawned service ended in a non-zero state."""


class SwarmTimeoutError(SwarmServiceError):
    """`wait_for` exceeded its timeout before the task reached a terminal state."""


@dataclass(frozen=True)
class SpawnedService:
    service_id: str
    name: str
    job_id: str
    agent: str


TERMINAL_STATES = frozenset({"complete", "failed", "shutdown", "rejected", "orphaned"})


class _ServiceProtocol(Protocol):
    id: str
    name: str

    def tasks(self) -> list[dict[str, Any]]: ...
    def remove(self) -> None: ...


class _ServicesProtocol(Protocol):
    def create(self, **kwargs: Any) -> _ServiceProtocol: ...
    def get(self, service_id: str) -> _ServiceProtocol: ...
    def list(self, filters: dict[str, str] | None = None) -> list[_ServiceProtocol]: ...


class _DockerClientProtocol(Protocol):
    @property
    def services(self) -> _ServicesProtocol: ...


class SwarmManager:
    DEFAULT_IMAGE = "agent-swarm:latest"
    DEFAULT_VOLUME = "agent-swarm_shared-data"
    DEFAULT_LABEL_PREFIX = "agent-swarm"

    def __init__(
        self,
        client: _DockerClientProtocol | None = None,
        image: str = DEFAULT_IMAGE,
        shared_volume: str = DEFAULT_VOLUME,
        data_root_in_container: str = "/app/data",
        label_prefix: str = DEFAULT_LABEL_PREFIX,
        poll_interval_s: float = 0.5,
        reap_stale_on_startup: bool = True,
        logger: SwarmEventLogger | None = None,
    ) -> None:
        self._client = client if client is not None else _resolve_default_client()
        self._image = image
        self._shared_volume = shared_volume
        self._data_root = data_root_in_container
        self._label_prefix = label_prefix
        self._poll_interval = poll_interval_s
        self._logger = logger or SwarmEventLogger.silent()
        if reap_stale_on_startup:
            self.reap_stale()

    # ----- spawn -----------------------------------------------------------

    def build_spec(
        self,
        agent_name: str,
        job_id: str,
        extra_env: dict[str, str] | None = None,
    ) -> ServiceSpec:
        labels = {
            f"{self._label_prefix}.job-id": job_id,
            f"{self._label_prefix}.agent": agent_name,
            f"{self._label_prefix}.role": "ephemeral",
        }
        env: dict[str, str] = {"DATA_ROOT": self._data_root}
        # Forward LLM credentials from our environment so the spawned agent
        # service can construct its own LLMClient. Empty/unset vars are skipped.
        for key in PROPAGATED_ENV_VARS:
            value = os.environ.get(key, "")
            if value:
                env[key] = value
        if extra_env:
            env.update(extra_env)
        return ServiceSpec(
            image=self._image,
            command=[
                "python",
                "-m",
                "agents.runner",
                "--agent",
                agent_name,
                "--job",
                job_id,
            ],
            name=f"{self._label_prefix}-{agent_name}-{job_id}-{uuid4().hex[:6]}",
            labels=labels,
            env=env,
            mounts=[f"{self._shared_volume}:{self._data_root}:rw"],
            restart_condition="none",
        )

    def spawn_agent(
        self,
        agent_name: str,
        job_id: str,
        extra_env: dict[str, str] | None = None,
    ) -> SpawnedService:
        spec = self.build_spec(agent_name, job_id, extra_env)
        service = self._client.services.create(**spec.to_create_kwargs())
        return SpawnedService(
            service_id=service.id,
            name=service.name,
            job_id=job_id,
            agent=agent_name,
        )

    # ----- wait ------------------------------------------------------------

    def wait_for(self, service: SpawnedService, timeout_s: float = 60.0) -> int:
        deadline = time.monotonic() + timeout_s
        last_state = "pending"
        while time.monotonic() < deadline:
            try:
                live = self._client.services.get(service.service_id)
            except Exception as exc:  # noqa: BLE001 — SDK exceptions vary
                raise SwarmServiceError(
                    f"Service {service.name} disappeared: {exc}"
                ) from exc

            for task in live.tasks():
                state = (task.get("Status") or {}).get("State")
                if state in TERMINAL_STATES:
                    exit_code = (
                        ((task.get("Status") or {}).get("ContainerStatus") or {}).get(
                            "ExitCode", 0
                        )
                    )
                    return int(exit_code)
                if state:
                    last_state = state
            time.sleep(self._poll_interval)
        raise SwarmTimeoutError(
            f"Service {service.name} stuck in {last_state!r} after {timeout_s}s"
        )

    # ----- cleanup ---------------------------------------------------------

    def cleanup(self, service: SpawnedService) -> None:
        """Idempotent — swallows 'not found' / already-removed errors."""
        try:
            live = self._client.services.get(service.service_id)
            live.remove()
        except Exception:  # noqa: BLE001
            pass

    def reap_stale(self) -> int:
        """Remove any leftover ephemeral services from a prior run.

        Called automatically at construction unless `reap_stale_on_startup=False`.
        Useful after a crashed supervisor: ensures `docker service ls` is clean
        before the next run spawns fresh agents. Returns the count removed.
        """
        stale = self.list_active({f"{self._label_prefix}.role": "ephemeral"})
        for s in stale:
            self.cleanup(s)
        self._logger.reap(len(stale))
        return len(stale)

    def list_active(
        self, label_filter: dict[str, str] | None = None
    ) -> list[SpawnedService]:
        filters: dict[str, str] = {}
        if label_filter:
            for k, v in label_filter.items():
                filters["label"] = f"{k}={v}"
        services = self._client.services.list(filters=filters or None)
        out: list[SpawnedService] = []
        for s in services:
            labels = getattr(s, "labels", {}) or {}
            out.append(
                SpawnedService(
                    service_id=s.id,
                    name=s.name,
                    job_id=labels.get(f"{self._label_prefix}.job-id", ""),
                    agent=labels.get(f"{self._label_prefix}.agent", ""),
                )
            )
        return out


def _resolve_default_client() -> _DockerClientProtocol:
    import docker

    return docker.from_env()
