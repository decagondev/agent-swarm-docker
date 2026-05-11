"""Agent package.

Concrete agent modules are imported here for their `@register_agent`
side-effect — importing `agents` populates the module-level `REGISTRY`.
"""

from agents import (  # noqa: F401 — import-for-side-effect (@register_agent)
    capitalize,
    count_consonants,
    feature_extractor,
    reverse,
    slogan_generator,
    translator,
    vowel_random,
)
from agents.base import AgentResult, BaseAgent, ToolSchema

__all__ = ["AgentResult", "BaseAgent", "ToolSchema"]
