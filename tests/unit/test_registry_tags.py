"""Tag-based filtering on AgentRegistry.openai_tools / all_schemas."""

from pathlib import Path

import pytest

from agents.base import AgentResult, BaseAgent
from core.registry import AgentRegistry


def _make_agent(agent_name: str, tags: frozenset[str]) -> type[BaseAgent]:
    class _A(BaseAgent):
        name = agent_name
        description = f"Test agent {agent_name}."
        parameters = {"type": "object", "properties": {}}

    _A.tags = tags
    _A.__name__ = f"_Agent_{agent_name}"

    def _run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
        return AgentResult(self.name, job_id, output_dir / "x", "ok")

    _A.run = _run  # type: ignore[method-assign]
    return _A


def _populate() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(_make_agent("g1", frozenset({"general"})))
    reg.register(_make_agent("g2", frozenset({"general"})))
    reg.register(_make_agent("p1", frozenset({"pentest"})))
    reg.register(_make_agent("multi", frozenset({"general", "pentest"})))
    return reg


def test_include_tags_none_returns_all():
    reg = _populate()
    names = [t["function"]["name"] for t in reg.openai_tools()]
    assert names == ["g1", "g2", "multi", "p1"]


def test_general_only_excludes_pentest():
    reg = _populate()
    names = [
        t["function"]["name"]
        for t in reg.openai_tools(include_tags=frozenset({"general"}))
    ]
    assert names == ["g1", "g2", "multi"]
    assert "p1" not in names


def test_pentest_only_excludes_general_only_agents():
    reg = _populate()
    names = [
        t["function"]["name"]
        for t in reg.openai_tools(include_tags=frozenset({"pentest"}))
    ]
    assert names == ["multi", "p1"]


def test_both_tags_returns_union():
    reg = _populate()
    names = [
        t["function"]["name"]
        for t in reg.openai_tools(include_tags=frozenset({"general", "pentest"}))
    ]
    assert names == ["g1", "g2", "multi", "p1"]


def test_empty_frozenset_raises_value_error():
    reg = _populate()
    with pytest.raises(ValueError, match="non-empty"):
        reg.openai_tools(include_tags=frozenset())
    with pytest.raises(ValueError, match="non-empty"):
        reg.all_schemas(include_tags=frozenset())


def test_all_schemas_filter_matches_openai_tools_filter():
    reg = _populate()
    schemas = reg.all_schemas(include_tags=frozenset({"general"}))
    tools = reg.openai_tools(include_tags=frozenset({"general"}))
    assert [s.name for s in schemas] == [t["function"]["name"] for t in tools]


def test_default_base_agent_tag_is_general():
    """Untouched agents (no tags override) must keep behaving as today."""
    from agents.base import BaseAgent as _BaseAgent

    assert _BaseAgent.tags == frozenset({"general"})


def test_pentest_agents_are_pentest_tagged():
    """Sanity check on the live registry: nmap_scan + pentest_reporter
    must carry the pentest tag so the --pentest flag actually gates them."""
    import agents  # noqa: F401 — populate REGISTRY
    from core.registry import REGISTRY

    assert REGISTRY.get("nmap_scan").tags == frozenset({"pentest"})
    assert REGISTRY.get("pentest_reporter").tags == frozenset({"pentest"})


def test_normal_path_unchanged_by_filter():
    """The seven existing agents must still appear in a --pentest-less run."""
    import agents  # noqa: F401
    from core.registry import REGISTRY

    legacy_names = {
        t["function"]["name"]
        for t in REGISTRY.openai_tools(include_tags=frozenset({"general"}))
    }
    assert {
        "capitalize",
        "count_consonants",
        "feature_extractor",
        "reverse",
        "slogan_generator",
        "translator",
        "vowel_random",
    } <= legacy_names
    assert "nmap_scan" not in legacy_names
    assert "pentest_reporter" not in legacy_names
