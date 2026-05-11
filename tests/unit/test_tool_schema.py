"""Tests for `ToolSchema.to_openai_dict()` + `AgentRegistry.openai_tools()` + prompt."""

import agents  # noqa: F401 — triggers @register_agent
from agents.base import ToolSchema
from core.registry import REGISTRY
from core.supervisor import SUPERVISOR_SYSTEM_PROMPT, build_user_message


def test_to_openai_dict_shape():
    schema = ToolSchema(
        name="capitalize",
        description="Uppercase the input.",
        parameters={
            "type": "object",
            "properties": {"input_ref": {"type": "string"}},
            "required": ["input_ref"],
        },
    )
    out = schema.to_openai_dict()

    assert out["type"] == "function"
    assert out["function"]["name"] == "capitalize"
    assert out["function"]["description"] == "Uppercase the input."
    assert out["function"]["parameters"]["properties"]["input_ref"]["type"] == "string"
    assert out["function"]["parameters"]["required"] == ["input_ref"]


def test_to_openai_dict_round_trips_parameters_identity():
    params = {"type": "object", "properties": {}, "required": []}
    schema = ToolSchema(name="x", description="d", parameters=params)
    # The dict is passed through unmodified so deep equality holds.
    assert schema.to_openai_dict()["function"]["parameters"] == params


def test_registry_openai_tools_returns_list_per_agent():
    tools = REGISTRY.openai_tools()
    names = [t["function"]["name"] for t in tools]
    assert names == sorted(names)  # Stable order.
    assert set(names) == {"capitalize", "count_consonants", "reverse", "vowel_random"}


def test_registry_openai_tools_are_function_typed():
    for tool in REGISTRY.openai_tools():
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]


def test_supervisor_system_prompt_mentions_parallel_and_input_ref():
    # Guard against accidental rewording that loses the parallelism instruction.
    assert "parallel" in SUPERVISOR_SYSTEM_PROMPT.lower()
    assert "input_ref" in SUPERVISOR_SYSTEM_PROMPT


def test_build_user_message_threads_job_id():
    msg = build_user_message("Analyze this text.", job_id="job-42")
    assert "job-42" in msg
    assert "Analyze this text." in msg
    assert "input_ref='job-42'" in msg
