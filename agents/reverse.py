"""Reverse agent — emits the input text reversed character-by-character."""

from pathlib import Path

from agents.base import AgentResult, BaseAgent
from core.registry import register_agent


@register_agent
class ReverseAgent(BaseAgent):
    name = "reverse"
    description = "Reverse the input text character-by-character."
    parameters = {
        "type": "object",
        "properties": {
            "input_ref": {
                "type": "string",
                "description": "Job id whose input file should be transformed.",
            }
        },
        "required": ["input_ref"],
    }

    def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
        text = input_path.read_text(encoding="utf-8")
        result = text[::-1]

        output_path = output_dir / f"{job_id}__{self.name}.result"
        output_path.write_text(result, encoding="utf-8")

        return AgentResult(
            agent_name=self.name,
            job_id=job_id,
            output_path=output_path,
            summary=f"REVERSED → {len(result)} chars",
        )
