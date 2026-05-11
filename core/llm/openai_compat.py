"""Shared base for the three OpenAI-API-compatible providers.

OpenAI, Groq, and xAI all speak the same chat-completions wire protocol — only
the base URL and the env var holding the API key differ. Subclasses set three
ClassVars and the rest is shared here.
"""

import json
import os
from typing import Any, ClassVar

from openai import OpenAI

from core.llm.base import LLMClient, LLMResponse, ToolCall, ToolResult


class MissingAPIKeyError(RuntimeError):
    """Raised when the provider's API key env var is unset or empty."""


class _OpenAICompatibleClient(LLMClient):
    BASE_URL: ClassVar[str | None] = None       # None = SDK default (api.openai.com)
    API_KEY_ENV: ClassVar[str] = ""             # subclass override
    DEFAULT_MODEL: ClassVar[str] = ""           # subclass override

    def __init__(self, model: str | None = None, client: OpenAI | None = None) -> None:
        api_key = os.environ.get(self.API_KEY_ENV, "").strip()
        if not api_key and client is None:
            raise MissingAPIKeyError(
                f"Environment variable {self.API_KEY_ENV} is not set."
            )
        self._client = client or OpenAI(api_key=api_key, base_url=self.BASE_URL)
        self._model = model or os.environ.get("LLM_MODEL") or self.DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult] | None = None,
    ) -> LLMResponse:
        full_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        full_messages.extend(messages)
        if tool_results:
            full_messages.extend(
                {
                    "role": "tool",
                    "tool_call_id": tr.tool_call_id,
                    "content": tr.content,
                }
                for tr in tool_results
            )

        kwargs: dict[str, Any] = {"model": self._model, "messages": full_messages}
        if tools:
            kwargs["tools"] = tools

        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls = tuple(
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in (msg.tool_calls or [])
        )

        return LLMResponse(
            text=msg.content,
            tool_calls=tool_calls,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else {},
        )
