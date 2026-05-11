"""Agent package.

Concrete agent modules are imported here for their `@register_agent`
side-effect — importing `agents` populates the module-level `REGISTRY`.
"""

from agents import capitalize, reverse  # noqa: F401 — import-for-side-effect
from agents.base import AgentResult, BaseAgent, ToolSchema

__all__ = ["AgentResult", "BaseAgent", "ToolSchema"]
