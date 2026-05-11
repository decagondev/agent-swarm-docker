"""Tests for the OpenAI/Groq/xAI provider adapters and `get_llm_client` factory.

We mock the `OpenAI` SDK class at its import site rather than mocking HTTP —
the SDK uses httpx and our deliverable for this slice is the URL/auth/parse
contract, which is observable at the SDK constructor + response-parse layer.
"""

from types import SimpleNamespace

import pytest

from core.llm import (
    PROVIDER_NAMES,
    UnknownProviderError,
    get_llm_client,
)
from core.llm.base import LLMResponse, ToolResult
from core.llm.groq_client import GroqClient
from core.llm.openai_client import OpenAIClient
from core.llm.openai_compat import MissingAPIKeyError
from core.llm.xai_client import XAIClient


def _make_sdk_response(content="ok", tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg)],
        model_dump=lambda: {"id": "test-resp"},
    )


@pytest.fixture
def patched_openai(mocker):
    """Patch the `OpenAI` constructor in openai_compat. Returns the mock class."""
    mock_cls = mocker.patch("core.llm.openai_compat.OpenAI", autospec=False)
    instance = mock_cls.return_value
    instance.chat.completions.create.return_value = _make_sdk_response()
    return mock_cls


@pytest.mark.parametrize(
    "cls,env_var,base_url,default_model",
    [
        (OpenAIClient, "OPENAI_API_KEY", None, "gpt-4o-mini"),
        (GroqClient, "GROQ_API_KEY", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
        (XAIClient, "XAI_API_KEY", "https://api.x.ai/v1", "grok-2-latest"),
    ],
)
def test_provider_uses_correct_base_url_and_key(
    cls, env_var, base_url, default_model, monkeypatch, patched_openai
):
    monkeypatch.setenv(env_var, "test-key-123")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    client = cls()

    patched_openai.assert_called_once_with(api_key="test-key-123", base_url=base_url)
    assert client.model == default_model


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError, match="OPENAI_API_KEY"):
        OpenAIClient()


def test_model_override_via_env(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-future")
    assert OpenAIClient().model == "gpt-5-future"


def test_model_override_via_kwarg(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert OpenAIClient(model="custom-model").model == "custom-model"


def test_chat_builds_messages_with_system_prompt(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    OpenAIClient().chat(
        system="you are helpful",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
    )

    create = patched_openai.return_value.chat.completions.create
    create.assert_called_once()
    kwargs = create.call_args.kwargs
    assert kwargs["messages"][0] == {"role": "system", "content": "you are helpful"}
    assert kwargs["messages"][1] == {"role": "user", "content": "hi"}
    assert "tools" not in kwargs  # Omitted when empty.


def test_chat_includes_tools_when_provided(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    schema = [{"type": "function", "function": {"name": "x", "parameters": {}}}]
    OpenAIClient().chat(system="s", messages=[], tools=schema)

    create = patched_openai.return_value.chat.completions.create
    assert create.call_args.kwargs["tools"] == schema


def test_chat_splices_tool_results_as_tool_messages(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    OpenAIClient().chat(
        system="s",
        messages=[{"role": "user", "content": "go"}],
        tools=[],
        tool_results=[ToolResult(tool_call_id="t1", content="42")],
    )

    msgs = patched_openai.return_value.chat.completions.create.call_args.kwargs["messages"]
    tool_msg = next(m for m in msgs if m["role"] == "tool")
    assert tool_msg == {"role": "tool", "tool_call_id": "t1", "content": "42"}


def test_response_parses_text_only(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    patched_openai.return_value.chat.completions.create.return_value = _make_sdk_response(
        content="final answer"
    )

    resp = OpenAIClient().chat(system="s", messages=[], tools=[])

    assert isinstance(resp, LLMResponse)
    assert resp.text == "final answer"
    assert resp.tool_calls == ()
    assert resp.is_final


def test_response_parses_tool_calls(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    tc = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="capitalize", arguments='{"input_ref": "job-1"}'),
    )
    patched_openai.return_value.chat.completions.create.return_value = _make_sdk_response(
        content=None, tool_calls=[tc]
    )

    resp = OpenAIClient().chat(system="s", messages=[], tools=[])

    assert resp.text is None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].id == "call_1"
    assert resp.tool_calls[0].name == "capitalize"
    assert resp.tool_calls[0].arguments == {"input_ref": "job-1"}
    assert resp.is_final is False


def test_response_parses_empty_arguments(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    tc = SimpleNamespace(id="c", function=SimpleNamespace(name="x", arguments=""))
    patched_openai.return_value.chat.completions.create.return_value = _make_sdk_response(
        content=None, tool_calls=[tc]
    )

    resp = OpenAIClient().chat(system="s", messages=[], tools=[])
    assert resp.tool_calls[0].arguments == {}


def test_factory_dispatches_each_provider(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("XAI_API_KEY", "k")

    assert isinstance(get_llm_client("openai"), OpenAIClient)
    assert isinstance(get_llm_client("groq"), GroqClient)
    assert isinstance(get_llm_client("xai"), XAIClient)


def test_factory_falls_back_to_env(monkeypatch, patched_openai):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    assert isinstance(get_llm_client(), OpenAIClient)


def test_factory_unknown_provider_raises(monkeypatch):
    with pytest.raises(UnknownProviderError, match="claude"):
        get_llm_client("claude")


def test_factory_missing_provider_raises(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with pytest.raises(UnknownProviderError, match="not specified"):
        get_llm_client()


def test_provider_names_constant():
    assert PROVIDER_NAMES == ("openai", "groq", "xai")
