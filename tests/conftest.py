"""Shared pytest fixtures."""

import os
from typing import Any

import pytest

from core.llm.base import LLMClient, LLMResponse, ToolResult


class FakeLLMClient(LLMClient):
    """Scripted `LLMClient` for tests.

    Queue a series of `LLMResponse` objects via `queue_response()`; each call
    to `chat()` pops the next one. All calls are recorded on `self.calls`
    so tests can assert what the Supervisor sent.
    """

    def __init__(self) -> None:
        self._responses: list[LLMResponse] = []
        self.calls: list[dict[str, Any]] = []

    def queue_response(self, response: LLMResponse) -> None:
        self._responses.append(response)

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult] | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system": system,
                "messages": messages,
                "tools": tools,
                "tool_results": tool_results,
            }
        )
        if not self._responses:
            raise AssertionError("FakeLLMClient.chat called with no queued responses")
        return self._responses.pop(0)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


# ---------------------------------------------------------------------------
# Docker SDK fake — used by SwarmManager tests.
# ---------------------------------------------------------------------------


class FakeService:
    def __init__(
        self,
        id_: str,
        name: str,
        labels: dict[str, str],
        tasks: list[dict[str, Any]] | None = None,
    ) -> None:
        self.id = id_
        self.name = name
        self.labels = labels
        self._tasks = tasks if tasks is not None else [{"Status": {"State": "complete"}}]
        self.removed = False

    def tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)

    def set_tasks(self, tasks: list[dict[str, Any]]) -> None:
        self._tasks = tasks

    def remove(self) -> None:
        self.removed = True


class FakeServices:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self._services: dict[str, FakeService] = {}
        self._counter = 0

    def create(self, **kwargs: Any) -> FakeService:
        self._counter += 1
        sid = f"svc-{self._counter:04d}"
        svc = FakeService(
            id_=sid,
            name=kwargs.get("name", sid),
            labels=dict(kwargs.get("labels", {})),
        )
        self._services[sid] = svc
        self.create_calls.append(kwargs)
        return svc

    def get(self, service_id: str) -> FakeService:
        if service_id not in self._services:
            raise KeyError(service_id)
        return self._services[service_id]

    def list(self, filters: dict[str, str] | None = None) -> list[FakeService]:
        out = list(s for s in self._services.values() if not s.removed)
        if filters and "label" in filters:
            want = filters["label"]
            key, _, value = want.partition("=")
            out = [s for s in out if s.labels.get(key) == value]
        return out


class FakeDockerClient:
    def __init__(self) -> None:
        self.services = FakeServices()


@pytest.fixture
def fake_docker() -> FakeDockerClient:
    return FakeDockerClient()


@pytest.fixture
def shared_data_dir(tmp_path):
    """Throwaway shared-volume root mirroring /app/data layout in containers."""
    for sub in ("input", "results", "output"):
        (tmp_path / sub).mkdir()
    return tmp_path


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.integration tests unless DOCKER_SWARM_TESTS=1."""
    if os.environ.get("DOCKER_SWARM_TESTS") == "1":
        return
    skip_marker = pytest.mark.skip(reason="integration tests require DOCKER_SWARM_TESTS=1")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)
