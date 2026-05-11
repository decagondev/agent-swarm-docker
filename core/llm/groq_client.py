"""Groq provider adapter — OpenAI-API-compatible at api.groq.com/openai/v1."""

from core.llm.openai_compat import _OpenAICompatibleClient


class GroqClient(_OpenAICompatibleClient):
    BASE_URL = "https://api.groq.com/openai/v1"
    API_KEY_ENV = "GROQ_API_KEY"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
