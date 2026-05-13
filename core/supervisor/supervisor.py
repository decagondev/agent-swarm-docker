"""Supervisor — composes LLMClient + AgentRegistry + executor + SharedVolume.

This module hosts both the `Supervisor` class and the in-process
`ThreadPoolAgentExecutor`. Epic 3 swaps the executor implementation for one
backed by Docker Swarm services; the Supervisor itself never imports `docker`.
"""

from __future__ import annotations

import inspect
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol
from uuid import uuid4

from agents.base import AgentResult, BaseAgent
from core.io.shared_volume import SharedVolume
from core.llm.base import LLMClient
from core.logging import SwarmEventLogger
from core.registry import AgentRegistry
from core.supervisor.aggregator import (
    build_assistant_tool_call_message,
    build_tool_result_messages,
)
from core.supervisor.prompt import SUPERVISOR_SYSTEM_PROMPT, build_user_message
from core.swarm import ResultWatcher, SwarmManager

MAX_ITERATIONS = 5
DEFAULT_MAX_WORKERS = 8
DEFAULT_SWARM_AGENT_TIMEOUT_S = 120.0
DEFAULT_SUMMARY_CLIP_CHARS = 800


def _instantiate(
    cls: type[BaseAgent],
    llm: LLMClient | None,
    volume: SharedVolume | None = None,
) -> BaseAgent:
    """Construct an agent, injecting `llm` / `volume` only if accepted.

    Mirrors the Dependency-Inversion pattern: simple agents declare neither
    parameter and stay constructible with zero args; LLM-aware agents declare
    `llm=`; cross-agent-reading agents declare `volume=`. Each kwarg is added
    independently based on the actual __init__ signature.
    """
    params = inspect.signature(cls.__init__).parameters
    kwargs: dict[str, Any] = {}
    if llm is not None and "llm" in params:
        kwargs["llm"] = llm
    if volume is not None and "volume" in params:
        kwargs["volume"] = volume
    return cls(**kwargs)


class AgentExecutor(Protocol):
    """Pluggable parallel executor for tool calls.

    `ThreadPoolAgentExecutor` is the in-process implementation; Epic 3
    introduces a Swarm-backed one with the same shape.
    """

    def execute(self, calls: list[tuple[str, str]]) -> list[AgentResult]: ...


class ThreadPoolAgentExecutor:
    """Run agents in-process across a thread pool, one task per tool call."""

    def __init__(
        self,
        registry: AgentRegistry,
        volume: SharedVolume,
        max_workers: int = DEFAULT_MAX_WORKERS,
        llm: LLMClient | None = None,
    ) -> None:
        self._registry = registry
        self._volume = volume
        self._max_workers = max_workers
        self._llm = llm

    def execute(self, calls: list[tuple[str, str]]) -> list[AgentResult]:
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = [pool.submit(self._run_one, name, job_id) for name, job_id in calls]
            return [f.result() for f in futures]

    def _run_one(self, agent_name: str, job_id: str) -> AgentResult:
        cls = self._registry.get(agent_name)
        return _instantiate(cls, self._llm, self._volume).run(
            self._volume.input_path(job_id),
            self._volume.results_dir,
            job_id,
        )


class SupervisorIterationLimitError(RuntimeError):
    """Raised when the LLM loop fails to converge on a final answer."""


class SwarmAgentExecutor:
    """Run agents as ephemeral Docker Swarm services.

    For each tool call: `SwarmManager.spawn_agent` creates a service, the
    `ResultWatcher` blocks until `<job>__<agent>.result` lands on the shared
    volume, then `SwarmManager.cleanup` removes the service. Spawning and
    waiting happen concurrently via a thread pool, so calls in the same LLM
    turn run in parallel.

    `AgentResult.summary` is the result-file contents (clipped). Swarm-spawned
    agents don't return Python objects, so the file *is* the wire format.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        volume: SharedVolume,
        swarm: SwarmManager,
        watcher: ResultWatcher,
        max_workers: int = DEFAULT_MAX_WORKERS,
        agent_timeout_s: float = DEFAULT_SWARM_AGENT_TIMEOUT_S,
        summary_clip_chars: int = DEFAULT_SUMMARY_CLIP_CHARS,
        logger: SwarmEventLogger | None = None,
    ) -> None:
        self._registry = registry  # Validation only — agent class must exist.
        self._volume = volume
        self._swarm = swarm
        self._watcher = watcher
        self._max_workers = max_workers
        self._agent_timeout_s = agent_timeout_s
        self._summary_clip = summary_clip_chars
        self._logger = logger or SwarmEventLogger.silent()

    def execute(self, calls: list[tuple[str, str]]) -> list[AgentResult]:
        # Validate up-front so a bad LLM-generated name doesn't waste a spawn.
        for name, _ in calls:
            self._registry.get(name)

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = [pool.submit(self._run_one, name, job_id) for name, job_id in calls]
            return [f.result() for f in futures]

    def _run_one(self, agent_name: str, job_id: str) -> AgentResult:
        start = time.monotonic()
        spawned = self._swarm.spawn_agent(agent_name, job_id)
        self._logger.spawn(agent_name, job_id, spawned.service_id)
        try:
            self._watcher.wait_for(job_id, agent_name, timeout_s=self._agent_timeout_s)
            self._logger.complete(agent_name, job_id, time.monotonic() - start)
        finally:
            self._swarm.cleanup(spawned)
            self._logger.cleanup(agent_name, job_id, spawned.service_id)

        result_path = self._volume.result_path(job_id, agent_name)
        body = result_path.read_text(encoding="utf-8") if result_path.exists() else ""
        clipped = body if len(body) <= self._summary_clip else body[: self._summary_clip] + "…"
        return AgentResult(
            agent_name=agent_name,
            job_id=job_id,
            output_path=result_path,
            summary=clipped,
        )


DEFAULT_ENABLED_TAGS = frozenset({"general"})


class Supervisor:
    def __init__(
        self,
        *,
        llm: LLMClient,
        registry: AgentRegistry,
        executor: AgentExecutor,
        volume: SharedVolume,
        max_iterations: int = MAX_ITERATIONS,
        logger: SwarmEventLogger | None = None,
        enabled_tags: frozenset[str] = DEFAULT_ENABLED_TAGS,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._executor = executor
        self._volume = volume
        self._max_iterations = max_iterations
        self._logger = logger or SwarmEventLogger.silent()
        self._enabled_tags = enabled_tags

    def run(self, user_prompt: str, *, job_id: str | None = None) -> str:
        if job_id is None:
            job_id = f"job-{uuid4().hex[:8]}"
        self._volume.write_input(job_id, user_prompt)

        tools = self._registry.openai_tools(include_tags=self._enabled_tags)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": build_user_message(user_prompt, job_id)},
        ]

        for iteration in range(self._max_iterations):
            resp = self._llm.chat(
                system=SUPERVISOR_SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            )
            if resp.is_final:
                self._logger.llm_final(iteration, len(resp.text or ""))
                return resp.text or ""

            self._logger.llm_round(iteration, len(resp.tool_calls))
            messages.append(build_assistant_tool_call_message(resp))
            calls = [(tc.name, job_id) for tc in resp.tool_calls]
            results = self._executor.execute(calls)
            messages.extend(build_tool_result_messages(resp.tool_calls, results))

        raise SupervisorIterationLimitError(
            f"LLM did not produce a final answer within {self._max_iterations} iterations."
        )


def _last_tool_call_names(messages: list[dict[str, Any]]) -> list[str]:
    """Test/debug helper — names of the most recent assistant turn's tool calls."""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            return [tc["function"]["name"] for tc in msg["tool_calls"]]
    return []


__all__ = [
    "AgentExecutor",
    "Supervisor",
    "SupervisorIterationLimitError",
    "SwarmAgentExecutor",
    "ThreadPoolAgentExecutor",
]
