"""Agent registry — Open/Closed extension point.

A new agent type is added by writing one file and decorating its class with
`@register_agent`. The registry itself never branches on agent name, so adding
agents requires no edits to the supervisor, swarm manager, or this module.

A module-level `REGISTRY` singleton is the default sink for `@register_agent`.
Tests construct their own `AgentRegistry()` to avoid leaking state between cases.
"""

from agents.base import BaseAgent, ToolSchema


class AgentAlreadyRegisteredError(ValueError):
    """Raised when two agent classes claim the same `name`."""


class AgentNotFoundError(KeyError):
    """Raised when `get()` is called with an unregistered name."""


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, type[BaseAgent]] = {}

    def register(self, cls: type[BaseAgent]) -> type[BaseAgent]:
        if cls.name in self._agents:
            raise AgentAlreadyRegisteredError(
                f"Agent {cls.name!r} already registered as {self._agents[cls.name].__name__}"
            )
        self._agents[cls.name] = cls
        return cls

    def get(self, name: str) -> type[BaseAgent]:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise AgentNotFoundError(f"No agent registered with name {name!r}") from exc

    def names(self) -> list[str]:
        return sorted(self._agents)

    def all_schemas(self) -> list[ToolSchema]:
        return [self._agents[name].tool_schema() for name in self.names()]

    def openai_tools(self) -> list[dict]:
        """All registered agents serialized for the LLM tools= parameter."""
        return [s.to_openai_dict() for s in self.all_schemas()]

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __len__(self) -> int:
        return len(self._agents)


REGISTRY = AgentRegistry()


def register_agent(cls: type[BaseAgent]) -> type[BaseAgent]:
    """Decorator form of `REGISTRY.register(cls)`."""
    return REGISTRY.register(cls)
