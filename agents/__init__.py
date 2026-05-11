"""Agent package.

Concrete agents land in later slices and self-register on import via
`@register_agent` (commit 3). Until then this package only exposes the
abstract `BaseAgent` and its data carriers.
"""

from agents.base import AgentResult, BaseAgent, ToolSchema

__all__ = ["AgentResult", "BaseAgent", "ToolSchema"]
