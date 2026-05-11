"""Tests for `SloganGeneratorAgent` — uses FakeLLMClient."""

import agents  # noqa: F401 — triggers @register_agent
from agents.slogan_generator import SloganGeneratorAgent
from core.llm.base import LLMResponse
from core.registry import REGISTRY


def test_writes_three_slogans(shared_data_dir, fake_llm):
    fake_llm.queue_response(
        LLMResponse(text="Slogan one!\nSlogan two!\nSlogan three!")
    )
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("Docker Swarm is great.", encoding="utf-8")

    result = SloganGeneratorAgent(llm=fake_llm).run(
        input_path, shared_data_dir / "results", "j"
    )

    body = result.output_path.read_text()
    assert body.count("\n") >= 2  # 3 lines → ≥ 2 newlines
    assert "SLOGANS" in result.summary


def test_uses_marketing_prompt(shared_data_dir, fake_llm):
    fake_llm.queue_response(LLMResponse(text="x"))
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("y", encoding="utf-8")

    SloganGeneratorAgent(llm=fake_llm).run(input_path, shared_data_dir / "results", "j")
    assert "slogan" in fake_llm.calls[0]["system"].lower()


def test_registered_with_singleton():
    assert "slogan_generator" in REGISTRY
    assert REGISTRY.get("slogan_generator") is SloganGeneratorAgent
