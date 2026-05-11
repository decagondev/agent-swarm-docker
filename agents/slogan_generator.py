"""Slogan-generator agent — uses an LLM to produce 3 marketing slogans."""

from pathlib import Path

from agents.base import AgentResult, BaseAgent
from core.llm.base import LLMClient
from core.registry import register_agent

_PROMPT = (
    "You are a marketing copywriter. Read the text and return exactly 3 "
    "catchy, punchy marketing slogans, one per line. No numbering, no extra prose."
)


@register_agent
class SloganGeneratorAgent(BaseAgent):
    name = "slogan_generator"
    description = "Generate three catchy marketing slogans inspired by the input text."
    parameters = {
        "type": "object",
        "properties": {
            "input_ref": {
                "type": "string",
                "description": "Job id whose input file should inspire the slogans.",
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
            summary=f"SLOGANS → {len(body)} chars",
        )


def _resolve_llm() -> LLMClient:
    from core.llm import get_llm_client

    return get_llm_client()
