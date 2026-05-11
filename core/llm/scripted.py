"""ScriptedLLMClient — replays a recorded conversation, used for offline rehearsal.

Loaded from a JSON fixture so the talk can run without network access (e.g.
when the conference WiFi is broken). Each fixture entry corresponds to one
`LLMClient.chat()` return value.

Fixture shape:
    {
      "responses": [
        {
          "text": null,
          "tool_calls": [
            {"id": "c1", "name": "capitalize", "arguments": {"input_ref": "j"}}
          ]
        },
        { "text": "Final report …" }
      ]
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.llm.base import LLMClient, LLMResponse, ToolCall, ToolResult


class ScriptedLLMExhaustedError(RuntimeError):
    """Raised when a `ScriptedLLMClient` is asked for more responses than recorded."""


class ScriptedLLMClient(LLMClient):
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._cursor = 0
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult] | None = None,
    ) -> LLMResponse:
        if self._cursor >= len(self._responses):
            raise ScriptedLLMExhaustedError(
                f"ScriptedLLMClient exhausted after {self._cursor} response(s); "
                "fixture is too short."
            )
        self.calls.append(
            {"system": system, "messages": messages, "tools": tools, "tool_results": tool_results}
        )
        resp = self._responses[self._cursor]
        self._cursor += 1
        return resp

    @classmethod
    def from_fixture(cls, path: Path | str) -> ScriptedLLMClient:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        responses = [_parse_response(entry) for entry in data.get("responses", [])]
        return cls(responses)


def _parse_response(entry: dict[str, Any]) -> LLMResponse:
    return LLMResponse(
        text=entry.get("text"),
        tool_calls=tuple(
            ToolCall(
                id=tc["id"],
                name=tc["name"],
                arguments=dict(tc.get("arguments", {})),
            )
            for tc in entry.get("tool_calls", [])
        ),
        raw=entry.get("raw", {}),
    )
