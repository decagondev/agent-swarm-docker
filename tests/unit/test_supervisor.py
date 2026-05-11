"""Tests for `Supervisor` driving `ThreadPoolAgentExecutor` against `FakeLLMClient`."""

import json

import pytest

import agents  # noqa: F401 — triggers @register_agent
from core.io.shared_volume import SharedVolume
from core.llm.base import LLMResponse, ToolCall
from core.registry import REGISTRY
from core.supervisor import (
    Supervisor,
    SupervisorIterationLimitError,
    ThreadPoolAgentExecutor,
)


@pytest.fixture
def volume(tmp_path):
    v = SharedVolume(tmp_path)
    v.ensure_dirs()
    return v


@pytest.fixture
def executor(volume):
    return ThreadPoolAgentExecutor(REGISTRY, volume, max_workers=4)


def _tool_call(call_id, name, **args):
    return ToolCall(id=call_id, name=name, arguments=args or {"input_ref": "j"})


def test_basic_flow_two_parallel_tools_then_final(volume, executor, fake_llm):
    fake_llm.queue_response(
        LLMResponse(
            text=None,
            tool_calls=(
                _tool_call("c1", "capitalize", input_ref="j"),
                _tool_call("c2", "reverse", input_ref="j"),
            ),
        )
    )
    fake_llm.queue_response(LLMResponse(text="Final report: done."))

    sup = Supervisor(llm=fake_llm, registry=REGISTRY, executor=executor, volume=volume)
    result = sup.run("Process: hello", job_id="j")

    assert "Final report" in result
    # Input file is the full user prompt; agents transform it byte-for-byte.
    assert (volume.results_dir / "j__capitalize.result").read_text() == "PROCESS: HELLO"
    assert (volume.results_dir / "j__reverse.result").read_text() == "olleh :ssecorP"
    # Both LLM calls happened.
    assert len(fake_llm.calls) == 2


def test_input_file_written_before_tools_run(volume, executor, fake_llm):
    fake_llm.queue_response(LLMResponse(text="ok"))
    Supervisor(llm=fake_llm, registry=REGISTRY, executor=executor, volume=volume).run(
        "Some text.", job_id="myjob"
    )
    assert volume.input_path("myjob").read_text() == "Some text."


def test_tool_call_history_passed_to_next_llm_turn(volume, executor, fake_llm):
    fake_llm.queue_response(
        LLMResponse(
            text=None, tool_calls=(_tool_call("c1", "capitalize"),)
        )
    )
    fake_llm.queue_response(LLMResponse(text="final"))

    Supervisor(llm=fake_llm, registry=REGISTRY, executor=executor, volume=volume).run(
        "go", job_id="j"
    )

    # Second call should see the assistant tool_call turn + the tool result.
    second_messages = fake_llm.calls[1]["messages"]
    roles = [m["role"] for m in second_messages]
    assert roles == ["user", "assistant", "tool"]

    assistant_msg = second_messages[1]
    assert assistant_msg["tool_calls"][0]["id"] == "c1"
    assert assistant_msg["tool_calls"][0]["function"]["name"] == "capitalize"
    # arguments are JSON-serialized for the wire.
    assert json.loads(assistant_msg["tool_calls"][0]["function"]["arguments"]) == {
        "input_ref": "j"
    }

    tool_msg = second_messages[2]
    assert tool_msg["tool_call_id"] == "c1"
    assert "CAPITALIZED" in tool_msg["content"]


def test_system_prompt_sent_each_turn(volume, executor, fake_llm):
    fake_llm.queue_response(LLMResponse(text="done"))
    Supervisor(llm=fake_llm, registry=REGISTRY, executor=executor, volume=volume).run(
        "x", job_id="j"
    )

    assert "Supervisor" in fake_llm.calls[0]["system"]
    assert "parallel" in fake_llm.calls[0]["system"].lower()


def test_tools_advertised_match_registry(volume, executor, fake_llm):
    fake_llm.queue_response(LLMResponse(text="done"))
    Supervisor(llm=fake_llm, registry=REGISTRY, executor=executor, volume=volume).run(
        "x", job_id="j"
    )

    tool_names = [t["function"]["name"] for t in fake_llm.calls[0]["tools"]]
    assert set(tool_names) == set(REGISTRY.names())


def test_iteration_limit_raises(volume, executor, fake_llm):
    # Always emit a tool call → never converges.
    looping_response = LLMResponse(
        text=None, tool_calls=(_tool_call("c1", "capitalize"),)
    )
    for _ in range(10):
        fake_llm.queue_response(looping_response)

    sup = Supervisor(
        llm=fake_llm,
        registry=REGISTRY,
        executor=executor,
        volume=volume,
        max_iterations=3,
    )
    with pytest.raises(SupervisorIterationLimitError, match="3 iterations"):
        sup.run("x", job_id="j")


def test_auto_generates_job_id_when_omitted(volume, executor, fake_llm):
    fake_llm.queue_response(LLMResponse(text="done"))
    Supervisor(llm=fake_llm, registry=REGISTRY, executor=executor, volume=volume).run("x")

    # Some input file under input/ was created with auto-generated id.
    written = list(volume.input_dir.glob("*.txt"))
    assert len(written) == 1
    assert written[0].read_text() == "x"


def test_threadpool_executor_runs_simple_agents(volume):
    """Smoke: the executor parallelizes the four LLM-free agents end-to-end."""
    volume.write_input("j", "Hello World")
    executor = ThreadPoolAgentExecutor(REGISTRY, volume)
    simple_agents = ["capitalize", "reverse", "count_consonants", "vowel_random"]
    results = executor.execute([(name, "j") for name in simple_agents])
    assert {r.agent_name for r in results} == set(simple_agents)
    for r in results:
        assert r.output_path.exists()


def test_threadpool_executor_injects_llm_into_llm_aware_agents(volume, fake_llm):
    """LLM-aware agents (feature_extractor, slogan_generator, translator) get
    the executor's `llm` injected via inspect-driven kwargs."""
    fake_llm.queue_response(LLMResponse(text="features list"))
    fake_llm.queue_response(LLMResponse(text="slogan A\nslogan B\nslogan C"))
    fake_llm.queue_response(LLMResponse(text="Salut le monde."))

    volume.write_input("j", "hello world")
    executor = ThreadPoolAgentExecutor(REGISTRY, volume, max_workers=1, llm=fake_llm)
    results = executor.execute(
        [("feature_extractor", "j"), ("slogan_generator", "j"), ("translator", "j")]
    )
    assert {r.agent_name for r in results} == {
        "feature_extractor", "slogan_generator", "translator"
    }
    for r in results:
        assert r.output_path.read_text() != ""
