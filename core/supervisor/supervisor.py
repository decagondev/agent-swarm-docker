"""Supervisor — composes LLMClient + AgentRegistry + executor + SharedVolume.

This module hosts both the `Supervisor` class and the in-process
`ThreadPoolAgentExecutor`. Epic 3 swaps the executor implementation for one
backed by Docker Swarm services; the Supervisor itself never imports `docker`.
"""

from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol
from uuid import uuid4

from agents.base import AgentResult, BaseAgent
from core.io.shared_volume import SharedVolume
from core.llm.base import LLMClient
from core.registry import AgentRegistry
from core.supervisor.aggregator import (
    build_assistant_tool_call_message,
    build_tool_result_messages,
)
from core.supervisor.prompt import SUPERVISOR_SYSTEM_PROMPT, build_user_message

MAX_ITERATIONS = 5
DEFAULT_MAX_WORKERS = 8


def _instantiate(cls: type[BaseAgent], llm: LLMClient | None) -> BaseAgent:
    """Construct an agent, passing `llm` only if its __init__ accepts it.

    Lets LLM-aware agents receive a shared client without forcing simple
    agents (e.g. CapitalizeAgent) to declare an `llm` parameter they ignore.
    """
    if llm is None or "llm" not in inspect.signature(cls.__init__).parameters:
        return cls()
    return cls(llm=llm)


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
        return _instantiate(cls, self._llm).run(
            self._volume.input_path(job_id),
            self._volume.results_dir,
            job_id,
        )


class SupervisorIterationLimitError(RuntimeError):
    """Raised when the LLM loop fails to converge on a final answer."""


class Supervisor:
    def __init__(
        self,
        *,
        llm: LLMClient,
        registry: AgentRegistry,
        executor: AgentExecutor,
        volume: SharedVolume,
        max_iterations: int = MAX_ITERATIONS,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._executor = executor
        self._volume = volume
        self._max_iterations = max_iterations

    def run(self, user_prompt: str, *, job_id: str | None = None) -> str:
        if job_id is None:
            job_id = f"job-{uuid4().hex[:8]}"
        self._volume.write_input(job_id, user_prompt)

        tools = self._registry.openai_tools()
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": build_user_message(user_prompt, job_id)},
        ]

        for _ in range(self._max_iterations):
            resp = self._llm.chat(
                system=SUPERVISOR_SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            )
            if resp.is_final:
                return resp.text or ""

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
    "ThreadPoolAgentExecutor",
]
