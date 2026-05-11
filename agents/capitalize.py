"""Capitalize agent — uppercases the input text."""

from pathlib import Path

from agents.base import AgentResult, BaseAgent
from core.registry import register_agent


@register_agent
class CapitalizeAgent(BaseAgent):
    name = "capitalize"
    description = "Uppercase the entire input text. Useful for emphasis or normalization."
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
        result = text.upper()

        output_path = output_dir / f"{job_id}__{self.name}.result"
        output_path.write_text(result, encoding="utf-8")

        return AgentResult(
            agent_name=self.name,
            job_id=job_id,
            output_path=output_path,
            summary=f"CAPITALIZED → {len(result)} chars",
        )
