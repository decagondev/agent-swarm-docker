"""LLM client abstractions.

The Supervisor depends on `LLMClient` (this module) rather than on any concrete
SDK. Provider adapters land in slice 11 alongside a `get_llm_client(provider)`
factory.
"""

from core.llm.base import LLMClient, LLMResponse, ToolCall, ToolResult

__all__ = ["LLMClient", "LLMResponse", "ToolCall", "ToolResult"]
