"""Supervisor package — composes LLMClient + AgentRegistry + executor."""

from core.supervisor.prompt import SUPERVISOR_SYSTEM_PROMPT, build_user_message
from core.supervisor.supervisor import (
    AgentExecutor,
    Supervisor,
    SupervisorIterationLimitError,
    ThreadPoolAgentExecutor,
)

__all__ = [
    "SUPERVISOR_SYSTEM_PROMPT",
    "AgentExecutor",
    "Supervisor",
    "SupervisorIterationLimitError",
    "ThreadPoolAgentExecutor",
    "build_user_message",
]
