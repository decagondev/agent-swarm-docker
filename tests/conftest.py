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
