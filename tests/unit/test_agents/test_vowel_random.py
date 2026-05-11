"""Tests for `VowelRandomAgent` — deterministic via seeded RNG."""

import random

import pytest

import agents  # noqa: F401 — triggers @register_agent
from agents.vowel_random import VowelRandomAgent, count_vowels
from core.registry import REGISTRY


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 0),
        ("bcdfg", 0),
        ("aeiou", 5),
        ("AEIOU", 5),
        ("Hello, World!", 3),  # e, o, o
        # Baseline uses literal set("aeiouAEIOU"); é is not in that set,
        # so it does not count as a vowel. Pinning baseline.
        ("café", 1),
    ],
)
def test_count_vowels_helper(text, expected):
    assert count_vowels(text) == expected


def test_deterministic_with_seeded_rng(shared_data_dir):
    text = "The quick brown fox."
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text(text, encoding="utf-8")

    a = VowelRandomAgent(rng=random.Random(42)).run(
        input_path, shared_data_dir / "results", "j1"
    )
    b = VowelRandomAgent(rng=random.Random(42)).run(
        input_path, shared_data_dir / "results", "j2"
    )

    assert a.output_path.read_text() == b.output_path.read_text()


def test_output_length_is_double_vowel_count(shared_data_dir):
    text = "The quick brown fox jumps over the lazy dog."  # 11 vowels
    expected_vowels = count_vowels(text)
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text(text, encoding="utf-8")

    result = VowelRandomAgent(rng=random.Random(0)).run(
        input_path, shared_data_dir / "results", "j"
    )

    output = result.output_path.read_text()
    assert len(output) == expected_vowels * 2
    assert result.summary == (
        f"VOWELS = {expected_vowels} → {expected_vowels * 2} random chars generated"
    )


def test_empty_input_produces_empty_output(shared_data_dir):
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("", encoding="utf-8")

    result = VowelRandomAgent(rng=random.Random(0)).run(
        input_path, shared_data_dir / "results", "j"
    )

    assert result.output_path.read_text() == ""


def test_output_only_alphanumerics(shared_data_dir):
    text = "aeiouAEIOU"  # plenty of vowels → plenty of random output
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text(text, encoding="utf-8")

    result = VowelRandomAgent(rng=random.Random(7)).run(
        input_path, shared_data_dir / "results", "j"
    )

    assert result.output_path.read_text().isalnum()


def test_registered_with_singleton():
    assert "vowel_random" in REGISTRY
    assert REGISTRY.get("vowel_random") is VowelRandomAgent
