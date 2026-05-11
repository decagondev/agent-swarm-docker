"""LLM client contract and message data carriers.

Every provider adapter (OpenAI, Groq, xAI in slice 11) implements `LLMClient`.
The Supervisor consumes this ABC so swapping providers is an env-var change.

Wire format note: `messages` and `tools` are passed through as OpenAI-style
dicts because Groq and xAI are OpenAI-API-compatible. Adapters translate at
the boundary only if a future provider diverges.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str | None
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_final(self) -> bool:
        """True when the model returned a final answer (no tool calls)."""
        return not self.tool_calls


class LLMClient(ABC):
    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult] | None = None,
    ) -> LLMResponse:
        """Single round-trip to the provider.

        - `system`: system prompt; rendered as the leading system message.
        - `messages`: prior conversation in OpenAI shape (`{role, content}` or
          a previous assistant turn containing `tool_calls`).
        - `tools`: tool schemas in OpenAI function-calling format.
        - `tool_results`: results of the prior turn's tool calls, if any.
          The adapter is responsible for splicing them into the request.
        """
