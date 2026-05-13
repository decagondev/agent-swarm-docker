"""Tests for `TranslatorAgent` — uses FakeLLMClient."""

import agents  # noqa: F401 — triggers @register_agent
from agents.translator import TranslatorAgent
from core.llm.base import LLMResponse
from core.registry import REGISTRY


def test_writes_translation(shared_data_dir, fake_llm):
    fake_llm.queue_response(LLMResponse(text="Le renard brun rapide."))
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("The quick brown fox.", encoding="utf-8")

    result = TranslatorAgent(llm=fake_llm).run(
        input_path, shared_data_dir / "results", "j"
    )

    assert result.output_path.read_text() == "Le renard brun rapide."
    assert "TRANSLATED" in result.summary
    assert "French" in result.summary


def test_prompt_pins_french(shared_data_dir, fake_llm):
    fake_llm.queue_response(LLMResponse(text="x"))
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("y", encoding="utf-8")

    TranslatorAgent(llm=fake_llm).run(input_path, shared_data_dir / "results", "j")
    assert "french" in fake_llm.calls[0]["system"].lower()


def test_registered_with_singleton():
    assert "translator" in REGISTRY
    assert REGISTRY.get("translator") is TranslatorAgent


def test_all_seven_general_agents_registered():
    """The seven 'general'-tagged agents must still be present and visible
    when the default (general-only) tag filter is applied."""
    expected_general = {
        "capitalize",
        "count_consonants",
        "feature_extractor",
        "reverse",
        "slogan_generator",
        "translator",
        "vowel_random",
    }
    general_names = {
        t["function"]["name"]
        for t in REGISTRY.openai_tools(include_tags=frozenset({"general"}))
    }
    assert general_names == expected_general
