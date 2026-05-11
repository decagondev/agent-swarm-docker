"""Tests for `AgentRegistry` and the `@register_agent` decorator."""

from pathlib import Path

import pytest

from agents.base import AgentResult, BaseAgent
from core.registry import (
    REGISTRY,
    AgentAlreadyRegisteredError,
    AgentNotFoundError,
    AgentRegistry,
    register_agent,
)


def _make_agent(agent_name: str) -> type[BaseAgent]:
    class _A(BaseAgent):
        name = agent_name
        description = f"Test agent {agent_name}."
        parameters = {"type": "object", "properties": {}}

        def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
            return AgentResult(self.name, job_id, output_dir / "x", "ok")

    _A.__name__ = f"_Agent_{agent_name}"
    return _A


def test_register_returns_class_unmodified():
    reg = AgentRegistry()
    agent_cls = _make_agent("a")
    assert reg.register(agent_cls) is agent_cls


def test_get_returns_registered_class():
    reg = AgentRegistry()
    agent_cls = _make_agent("a")
    reg.register(agent_cls)
    assert reg.get("a") is agent_cls


def test_duplicate_registration_raises():
    reg = AgentRegistry()
    reg.register(_make_agent("dup"))
    with pytest.raises(AgentAlreadyRegisteredError, match="dup"):
        reg.register(_make_agent("dup"))


def test_get_unregistered_raises():
    reg = AgentRegistry()
    with pytest.raises(AgentNotFoundError, match="missing"):
        reg.get("missing")


def test_names_sorted():
    reg = AgentRegistry()
    for n in ["zeta", "alpha", "mu"]:
        reg.register(_make_agent(n))
    assert reg.names() == ["alpha", "mu", "zeta"]


def test_all_schemas_one_per_class():
    reg = AgentRegistry()
    for n in ["a", "b", "c"]:
        reg.register(_make_agent(n))
    schemas = reg.all_schemas()
    assert [s.name for s in schemas] == ["a", "b", "c"]


def test_contains_and_len():
    reg = AgentRegistry()
    assert "x" not in reg
    assert len(reg) == 0
    reg.register(_make_agent("x"))
    assert "x" in reg
    assert len(reg) == 1


def test_register_agent_decorator_uses_module_singleton():
    # Snapshot the singleton so the test is hermetic.
    before = set(REGISTRY.names())
    try:
        @register_agent
        class _Tmp(BaseAgent):
            name = "__test_singleton__"
            description = "Singleton-decorator probe."
            parameters = {"type": "object", "properties": {}}

            def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
                return AgentResult(self.name, job_id, output_dir / "x", "ok")

        assert "__test_singleton__" in REGISTRY
        assert REGISTRY.get("__test_singleton__") is _Tmp
    finally:
        # Reach into the private dict to undo the side effect; preferable to
        # importing a teardown API just for tests.
        REGISTRY._agents.pop("__test_singleton__", None)
    assert set(REGISTRY.names()) == before
