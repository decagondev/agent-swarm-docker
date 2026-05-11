"""Tests for the `python supervisor.py` CLI."""

import subprocess
import sys
from pathlib import Path

import pytest

import supervisor as cli_module
from core.llm.base import LLMResponse, ToolCall

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def patched_llm(monkeypatch, fake_llm):
    """Wire `get_llm_client` calls inside supervisor.py to the FakeLLMClient."""
    monkeypatch.setattr(cli_module, "get_llm_client", lambda *a, **kw: fake_llm)
    return fake_llm


def test_help_runs_without_env(tmp_path):
    # --help short-circuits argparse before any LLM lookup.
    proc = subprocess.run(
        [sys.executable, "supervisor.py", "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert proc.returncode == 0
    assert "user task" in proc.stdout.lower()


def test_cli_runs_full_loop_with_fake_llm(tmp_path, patched_llm, capsys):
    patched_llm.queue_response(
        LLMResponse(
            text=None,
            tool_calls=(ToolCall(id="c1", name="capitalize", arguments={"input_ref": "j"}),),
        )
    )
    patched_llm.queue_response(LLMResponse(text="Final aggregated report."))

    rc = cli_module.main(
        [
            "--data-root", str(tmp_path),
            "--job", "j",
            "Capitalize the phrase: hello world",
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "Final aggregated report." in out
    assert (tmp_path / "input" / "j.txt").read_text() == (
        "Capitalize the phrase: hello world"
    )
    assert (tmp_path / "results" / "j__capitalize.result").exists()


def test_cli_joins_multi_word_prompt(tmp_path, patched_llm, capsys):
    patched_llm.queue_response(LLMResponse(text="ok"))

    cli_module.main(
        [
            "--data-root", str(tmp_path),
            "--job", "k",
            "The", "quick", "brown", "fox.",
        ]
    )

    assert (tmp_path / "input" / "k.txt").read_text() == "The quick brown fox."


def test_cli_provider_override_passed_through(tmp_path, monkeypatch, fake_llm):
    captured = {}

    def _stub(provider=None, **kw):
        captured["provider"] = provider
        return fake_llm

    monkeypatch.setattr(cli_module, "get_llm_client", _stub)
    fake_llm.queue_response(LLMResponse(text="done"))

    cli_module.main(
        ["--data-root", str(tmp_path), "--provider", "groq", "test prompt"]
    )

    assert captured["provider"] == "groq"
