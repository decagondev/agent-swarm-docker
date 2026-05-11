"""Tests for `FeatureExtractorAgent` — uses FakeLLMClient."""

import agents  # noqa: F401 — triggers @register_agent
from agents.feature_extractor import FeatureExtractorAgent
from core.llm.base import LLMResponse
from core.registry import REGISTRY


def test_writes_llm_response_to_result_file(shared_data_dir, fake_llm):
    fake_llm.queue_response(LLMResponse(text="- Speed: fast\n- Cost: cheap"))
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("Our product is fast and cheap.", encoding="utf-8")

    result = FeatureExtractorAgent(llm=fake_llm).run(
        input_path, shared_data_dir / "results", "j"
    )

    assert result.output_path.read_text() == "- Speed: fast\n- Cost: cheap"
    assert result.agent_name == "feature_extractor"
    assert "FEATURES" in result.summary
    # Verified the LLM was called with the input text.
    assert fake_llm.calls[0]["messages"][0]["content"] == "Our product is fast and cheap."


def test_empty_llm_response_handled(shared_data_dir, fake_llm):
    fake_llm.queue_response(LLMResponse(text=None))
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("x", encoding="utf-8")

    result = FeatureExtractorAgent(llm=fake_llm).run(
        input_path, shared_data_dir / "results", "j"
    )
    assert result.output_path.read_text() == ""
    assert "0 chars" in result.summary


def test_registered_with_singleton():
    assert "feature_extractor" in REGISTRY
    assert REGISTRY.get("feature_extractor") is FeatureExtractorAgent


def test_tool_schema_advertises_input_ref():
    schema = FeatureExtractorAgent.tool_schema()
    assert "input_ref" in schema.parameters["properties"]
