"""Translator agent — uses an LLM to translate input text to French.

Target language is hardcoded to French for the talk demo (per PRD §2 item 3).
A future slice can promote `target_language` to a tool-call parameter once
the supervisor pipes tool arguments through to `BaseAgent.run()`.
"""

from pathlib import Path

from agents.base import AgentResult, BaseAgent
from core.llm.base import LLMClient
from core.registry import register_agent

_TARGET_LANGUAGE = "French"
_PROMPT = (
    f"You are a professional translator. Translate the user's text into {_TARGET_LANGUAGE}. "
    "Return only the translation — no quotes, no notes, no prefatory phrases."
)


@register_agent
class TranslatorAgent(BaseAgent):
    name = "translator"
    description = f"Translate the input text into {_TARGET_LANGUAGE}."
    parameters = {
        "type": "object",
        "properties": {
            "input_ref": {
                "type": "string",
                "description": "Job id whose input file should be translated.",
            }
        },
        "required": ["input_ref"],
    }

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm

    def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
        text = input_path.read_text(encoding="utf-8")
        llm = self._llm or _resolve_llm()
        response = llm.chat(
            system=_PROMPT,
            messages=[{"role": "user", "content": text}],
            tools=[],
        )
        body = response.text or ""

        output_path = output_dir / f"{job_id}__{self.name}.result"
        output_path.write_text(body, encoding="utf-8")

        return AgentResult(
            agent_name=self.name,
            job_id=job_id,
            output_path=output_path,
            summary=f"TRANSLATED → {_TARGET_LANGUAGE} ({len(body)} chars)",
        )


def _resolve_llm() -> LLMClient:
    from core.llm import get_llm_client

    return get_llm_client()
