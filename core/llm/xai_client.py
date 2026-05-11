"""xAI provider adapter — OpenAI-API-compatible at api.x.ai/v1."""

from core.llm.openai_compat import _OpenAICompatibleClient


class XAIClient(_OpenAICompatibleClient):
    BASE_URL = "https://api.x.ai/v1"
    API_KEY_ENV = "XAI_API_KEY"
    DEFAULT_MODEL = "grok-2-latest"
