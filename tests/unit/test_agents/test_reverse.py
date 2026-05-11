"""Tests for `ReverseAgent` — pins the baseline reverse transform."""

import pytest

import agents  # noqa: F401 — triggers @register_agent
from agents.reverse import ReverseAgent
from core.registry import REGISTRY


@pytest.mark.parametrize(
    "text",
    [
        "",
        "abc",
        "The quick brown fox jumps over the lazy dog.",
        "Mixed CASE 123 — with non-ASCII: café, naïve.\nLine two.",
    ],
)
def test_byte_for_byte_parity_with_worker(text, shared_data_dir):
    # Baseline transform: `content[::-1]`.
    expected = text[::-1]

    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text(text, encoding="utf-8")

    result = ReverseAgent().run(input_path, shared_data_dir / "results", "job-1")

    assert result.output_path.read_bytes() == expected.encode("utf-8")
    assert result.agent_name == "reverse"
    assert result.job_id == "job-1"
    assert f"{len(expected)} chars" in result.summary


def test_registered_with_singleton():
    assert "reverse" in REGISTRY
    assert REGISTRY.get("reverse") is ReverseAgent


def test_tool_schema_advertises_input_ref():
    schema = ReverseAgent.tool_schema()
    assert schema.name == "reverse"
    assert "input_ref" in schema.parameters["properties"]


def test_palindrome_identity(shared_data_dir):
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("racecar", encoding="utf-8")

    result = ReverseAgent().run(input_path, shared_data_dir / "results", "j")

    assert result.output_path.read_text(encoding="utf-8") == "racecar"
