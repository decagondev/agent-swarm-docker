"""Tests for `CountConsonantsAgent` — parity with `worker.py`'s helper."""

import pytest

import agents  # noqa: F401 — triggers @register_agent
from agents.count_consonants import CountConsonantsAgent, count_consonants
from core.registry import REGISTRY


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 0),
        ("aeiou", 0),  # All vowels.
        ("AEIOU", 0),  # Vowels are case-insensitive in worker.py:15.
        ("bcdfg", 5),
        ("BCDFG", 5),
        ("Hello, World!", 7),  # H,l,l,W,r,l,d
        ("123 !@#", 0),  # Non-alpha skipped.
        # worker.py uses literal set("aeiouAEIOU"), so accented vowels like
        # é/ï are alpha-but-not-in-set → counted as consonants. Documenting
        # this pinned baseline behaviour.
        ("café naïve", 6),  # c,f,é + n,ï,v
    ],
)
def test_count_helper_parity(text, expected):
    assert count_consonants(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "The quick brown fox jumps over the lazy dog.",
        "Mixed CASE 123 — with non-ASCII: café, naïve.\nLine two.",
    ],
)
def test_agent_writes_count(text, shared_data_dir):
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text(text, encoding="utf-8")

    result = CountConsonantsAgent().run(input_path, shared_data_dir / "results", "j")

    assert result.output_path.read_text(encoding="utf-8") == str(count_consonants(text))
    assert result.agent_name == "count_consonants"
    assert result.summary == f"CONSONANTS = {count_consonants(text)}"


def test_registered_with_singleton():
    assert "count_consonants" in REGISTRY
    assert REGISTRY.get("count_consonants") is CountConsonantsAgent
