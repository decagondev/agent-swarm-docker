"""Tests for the abstract `BaseAgent` contract."""

import dataclasses
from pathlib import Path

import pytest

from agents.base import AgentResult, BaseAgent, ToolSchema


class _StubAgent(BaseAgent):
    name = "stub"
    description = "A trivial agent for testing."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
        output_path = output_dir / f"{job_id}__{self.name}.result"
        output_path.write_text(input_path.read_text())
        return AgentResult(
            agent_name=self.name,
            job_id=job_id,
            output_path=output_path,
            summary="stub ran",
        )


def test_tool_schema_built_from_classvars():
    schema = _StubAgent.tool_schema()
    assert isinstance(schema, ToolSchema)
    assert schema.name == "stub"
    assert schema.description == "A trivial agent for testing."
    assert schema.parameters["properties"]["text"]["type"] == "string"


def test_tool_schema_does_not_require_instantiation():
    # Critical for LLM-aware agents (Epic 2) that need deps at __init__.
    assert _StubAgent.tool_schema().name == "stub"


def test_abc_refuses_instantiation_without_run():
    class _Incomplete(BaseAgent):
        name = "incomplete"
        description = "Missing run()."
        parameters = {"type": "object", "properties": {}}

    with pytest.raises(TypeError, match="abstract"):
        _Incomplete()  # type: ignore[abstract]


def test_concrete_agent_runs_against_shared_volume(shared_data_dir, tmp_path):
    input_path = tmp_path / "in.txt"
    input_path.write_text("hello")

    result = _StubAgent().run(input_path, shared_data_dir / "results", "job-xyz")

    assert isinstance(result, AgentResult)
    assert result.agent_name == "stub"
    assert result.job_id == "job-xyz"
    assert result.output_path.read_text() == "hello"


def test_tool_schema_is_frozen():
    schema = _StubAgent.tool_schema()
    with pytest.raises(dataclasses.FrozenInstanceError):
        schema.name = "mutated"  # type: ignore[misc]


def test_agent_result_is_frozen():
    result = AgentResult(agent_name="x", job_id="y", output_path=Path("/tmp"), summary="s")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.summary = "mutated"  # type: ignore[misc]
