"""Conversation-history helpers for the Supervisor loop.

The OpenAI / Groq / xAI APIs require a specific shape for tool-call turns:
the assistant message that emits tool calls, then one `role=tool` message
per call carrying the result. These helpers build those messages from our
internal `LLMResponse` + `AgentResult` types.
"""

import json
from typing import Any

from agents.base import AgentResult
from core.llm.base import LLMResponse, ToolCall


def build_assistant_tool_call_message(response: LLMResponse) -> dict[str, Any]:
    """Render an `LLMResponse` with `tool_calls` as the assistant turn."""
    return {
        "role": "assistant",
        "content": response.text,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in response.tool_calls
        ],
    }


def build_tool_result_messages(
    tool_calls: tuple[ToolCall, ...] | list[ToolCall],
    results: list[AgentResult],
) -> list[dict[str, Any]]:
    """Pair each tool call with its `AgentResult.summary` as a tool message."""
    if len(tool_calls) != len(results):
        raise ValueError(
            f"tool_calls/results length mismatch: {len(tool_calls)} vs {len(results)}"
        )
    return [
        {
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result.summary,
        }
        for tc, result in zip(tool_calls, results, strict=True)
    ]
