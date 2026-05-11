"""LLM client abstractions + provider factory.

The Supervisor depends on `LLMClient` (this module) rather than on any concrete
SDK. Concrete adapters are imported lazily by `get_llm_client(provider)` so
importing `core.llm` doesn't drag in `openai` for callers that only need the
ABC and data carriers.
"""

import os

from core.llm.base import LLMClient, LLMResponse, ToolCall, ToolResult

__all__ = [
    "LLMClient",
    "LLMResponse",
    "PROVIDER_NAMES",
    "ToolCall",
    "ToolResult",
    "get_llm_client",
]

PROVIDER_NAMES = ("openai", "groq", "xai")


class UnknownProviderError(RuntimeError):
    """Raised when LLM_PROVIDER is unset or names an unknown provider."""


def get_llm_client(provider: str | None = None, **kwargs: object) -> LLMClient:
    """Construct an `LLMClient` for the named provider.

    `provider` falls back to the `LLM_PROVIDER` env var. Extra keyword args
    are forwarded to the concrete client's `__init__` (e.g. `model=...`).
    """
    name = (provider or os.environ.get("LLM_PROVIDER", "")).strip().lower()
    if name == "openai":
        from core.llm.openai_client import OpenAIClient
        return OpenAIClient(**kwargs)  # type: ignore[arg-type]
    if name == "groq":
        from core.llm.groq_client import GroqClient
        return GroqClient(**kwargs)  # type: ignore[arg-type]
    if name == "xai":
        from core.llm.xai_client import XAIClient
        return XAIClient(**kwargs)  # type: ignore[arg-type]
    if not name:
        raise UnknownProviderError(
            "LLM provider not specified; set LLM_PROVIDER or pass provider= explicitly."
        )
    raise UnknownProviderError(
        f"Unknown LLM provider {name!r}; expected one of {PROVIDER_NAMES}."
    )
