"""Supervisor package — composes LLMClient + AgentRegistry + executor.

The `Supervisor` class itself lands in slice 13; this module's currently
exposed surface is just the system prompt constants.
"""

from core.supervisor.prompt import SUPERVISOR_SYSTEM_PROMPT, build_user_message

__all__ = ["SUPERVISOR_SYSTEM_PROMPT", "build_user_message"]
