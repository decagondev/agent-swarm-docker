"""OpenAI provider adapter."""

from core.llm.openai_compat import _OpenAICompatibleClient


class OpenAIClient(_OpenAICompatibleClient):
    BASE_URL = None  # SDK default: https://api.openai.com/v1
    API_KEY_ENV = "OPENAI_API_KEY"
    DEFAULT_MODEL = "gpt-4o-mini"
