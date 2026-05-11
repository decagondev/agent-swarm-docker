"""Tests for the `LLMClient` ABC + frozen message data carriers."""

import dataclasses

import pytest

from core.llm.base import LLMClient, LLMResponse, ToolCall, ToolResult


def test_abc_refuses_instantiation_without_chat():
    with pytest.raises(TypeError, match="abstract"):
        LLMClient()  # type: ignore[abstract]


def test_fake_llm_client_satisfies_abc(fake_llm):
    # If FakeLLMClient didn't satisfy the ABC, the fixture itself would raise.
    assert isinstance(fake_llm, LLMClient)


def test_fake_llm_records_calls_and_returns_queued_response(fake_llm):
    fake_llm.queue_response(LLMResponse(text="hello"))
    resp = fake_llm.chat(system="sys", messages=[{"role": "user", "content": "hi"}], tools=[])

    assert resp.text == "hello"
    assert resp.is_final
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0]["system"] == "sys"


def test_fake_llm_chat_with_empty_queue_raises(fake_llm):
    with pytest.raises(AssertionError, match="no queued responses"):
        fake_llm.chat(system="s", messages=[], tools=[])


def test_tool_call_is_frozen():
    tc = ToolCall(id="abc", name="capitalize", arguments={"x": 1})
    with pytest.raises(dataclasses.FrozenInstanceError):
        tc.name = "other"  # type: ignore[misc]


def test_tool_result_is_frozen():
    tr = ToolResult(tool_call_id="abc", content="ok")
    with pytest.raises(dataclasses.FrozenInstanceError):
        tr.content = "mutated"  # type: ignore[misc]


def test_llm_response_is_final_when_no_tool_calls():
    assert LLMResponse(text="done").is_final is True


def test_llm_response_not_final_when_tool_calls_present():
    resp = LLMResponse(
        text=None,
        tool_calls=(ToolCall(id="1", name="capitalize", arguments={}),),
    )
    assert resp.is_final is False


def test_llm_response_equality_by_value():
    a = LLMResponse(text="hi", tool_calls=(ToolCall("1", "x", {"k": 1}),))
    b = LLMResponse(text="hi", tool_calls=(ToolCall("1", "x", {"k": 1}),))
    assert a == b


def test_tool_results_passed_through(fake_llm):
    fake_llm.queue_response(LLMResponse(text="ack"))
    results = [ToolResult(tool_call_id="t1", content="42")]
    fake_llm.chat(system="s", messages=[], tools=[], tool_results=results)
    assert fake_llm.calls[0]["tool_results"] == results
