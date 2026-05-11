"""Tests for `CapitalizeAgent` — parity with the original `worker.py` transform."""

import pytest

import agents  # noqa: F401 — triggers @register_agent
from agents.capitalize import CapitalizeAgent
from core.registry import REGISTRY


@pytest.mark.parametrize(
    "text",
    [
        "",
        "The quick brown fox jumps over the lazy dog.",
        "Mixed CASE 123 — with non-ASCII: café, naïve.\nLine two.",
        "already UPPER",
    ],
)
def test_byte_for_byte_parity_with_worker(text, shared_data_dir):
    # Equivalent to worker.py:36-38 — `result = content.upper()`.
    expected = text.upper()

    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text(text, encoding="utf-8")

    result = CapitalizeAgent().run(input_path, shared_data_dir / "results", "job-1")

    assert result.output_path.read_bytes() == expected.encode("utf-8")
    assert result.agent_name == "capitalize"
    assert result.job_id == "job-1"
    assert f"{len(expected)} chars" in result.summary


def test_registered_with_singleton():
    assert "capitalize" in REGISTRY
    assert REGISTRY.get("capitalize") is CapitalizeAgent


def test_tool_schema_advertises_input_ref():
    schema = CapitalizeAgent.tool_schema()
    assert schema.name == "capitalize"
    assert "input_ref" in schema.parameters["properties"]
    assert schema.parameters["required"] == ["input_ref"]


def test_output_path_uses_job_and_agent(shared_data_dir):
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("hi", encoding="utf-8")

    result = CapitalizeAgent().run(input_path, shared_data_dir / "results", "abc-123")

    assert result.output_path == shared_data_dir / "results" / "abc-123__capitalize.result"
