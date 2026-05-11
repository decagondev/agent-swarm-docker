"""Tests for `ScriptedLLMClient` + `supervisor.py --dry-run`."""

import json
from pathlib import Path

import pytest

import agents  # noqa: F401 — populates REGISTRY
import supervisor as cli_module
from core.llm.base import LLMResponse, ToolCall
from core.llm.scripted import ScriptedLLMClient, ScriptedLLMExhaustedError

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "talk_prompt_response.json"
)


# ----- ScriptedLLMClient unit tests ----------------------------------------


def test_replays_responses_in_order():
    a = LLMResponse(text="first")
    b = LLMResponse(text="second")
    client = ScriptedLLMClient([a, b])

    assert client.chat("s", [], []) is a
    assert client.chat("s", [], []) is b


def test_exhausted_raises():
    client = ScriptedLLMClient([LLMResponse(text="only")])
    client.chat("s", [], [])
    with pytest.raises(ScriptedLLMExhaustedError, match="exhausted after 1"):
        client.chat("s", [], [])


def test_records_calls():
    client = ScriptedLLMClient([LLMResponse(text="ok")])
    client.chat("sys-prompt", [{"role": "user", "content": "x"}], tools=[{"a": 1}])
    assert client.calls[0]["system"] == "sys-prompt"
    assert client.calls[0]["tools"] == [{"a": 1}]


def test_from_fixture_parses_tool_calls(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(
        json.dumps(
            {
                "responses": [
                    {
                        "text": None,
                        "tool_calls": [
                            {"id": "c1", "name": "capitalize", "arguments": {"input_ref": "j"}}
                        ],
                    },
                    {"text": "final"},
                ]
            }
        )
    )

    client = ScriptedLLMClient.from_fixture(p)
    first = client.chat("s", [], [])
    second = client.chat("s", [], [])

    assert isinstance(first.tool_calls[0], ToolCall)
    assert first.tool_calls[0].name == "capitalize"
    assert first.tool_calls[0].arguments == {"input_ref": "j"}
    assert second.text == "final"
    assert second.is_final


def test_from_fixture_empty_responses():
    """Path missing the 'responses' key produces an empty client (exhausted immediately)."""
    p = Path(__file__).parent / "_empty_fixture.json"
    p.write_text("{}")
    try:
        client = ScriptedLLMClient.from_fixture(p)
        with pytest.raises(ScriptedLLMExhaustedError):
            client.chat("s", [], [])
    finally:
        p.unlink(missing_ok=True)


# ----- talk fixture --------------------------------------------------------


def test_talk_fixture_loads():
    client = ScriptedLLMClient.from_fixture(FIXTURE_PATH)
    first = client.chat("s", [], [])
    # 4 parallel non-LLM agents — LLM-aware ones omitted on purpose (see fixture comment).
    assert len(first.tool_calls) == 4
    second = client.chat("s", [], [])
    assert "Final report" in (second.text or "")


def test_talk_fixture_only_uses_registered_agents():
    client = ScriptedLLMClient.from_fixture(FIXTURE_PATH)
    first = client.chat("s", [], [])
    from core.registry import REGISTRY

    for tc in first.tool_calls:
        assert tc.name in REGISTRY, f"Fixture references unregistered agent: {tc.name!r}"


# ----- CLI --dry-run integration --------------------------------------------


def test_dry_run_requires_fixture():
    with pytest.raises(SystemExit, match="--fixture"):
        cli_module.main(["--dry-run", "test prompt"])


def test_dry_run_end_to_end_no_network(tmp_path, capsys, monkeypatch):
    # Prove no provider lookup happened: blow up if get_llm_client is called.
    monkeypatch.setattr(
        cli_module, "get_llm_client",
        lambda *a, **kw: pytest.fail("get_llm_client called during --dry-run"),
    )

    rc = cli_module.main(
        [
            "--dry-run",
            "--fixture", str(FIXTURE_PATH),
            "--job", "demo",
            "--data-root", str(tmp_path),
            "--quiet",
            "The quick brown fox.",
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "Final report" in out
    # Agents really ran via the threadpool executor — result files exist.
    assert (tmp_path / "results" / "demo__capitalize.result").read_text() == "THE QUICK BROWN FOX."
    assert (tmp_path / "results" / "demo__reverse.result").read_text() == ".xof nworb kciuq ehT"
