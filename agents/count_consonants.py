"""Count-consonants agent — emits a decimal count of consonants in the input."""

from pathlib import Path

from agents.base import AgentResult, BaseAgent
from core.registry import register_agent

_VOWELS = frozenset("aeiouAEIOU")


def count_consonants(text: str) -> int:
    return sum(1 for c in text if c.isalpha() and c not in _VOWELS)


@register_agent
class CountConsonantsAgent(BaseAgent):
    name = "count_consonants"
    description = "Count the number of consonants (alphabetic non-vowels) in the input text."
    parameters = {
        "type": "object",
        "properties": {
            "input_ref": {
                "type": "string",
                "description": "Job id whose input file should be analysed.",
            }
        },
        "required": ["input_ref"],
    }

    def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
        text = input_path.read_text(encoding="utf-8")
        count = count_consonants(text)

        output_path = output_dir / f"{job_id}__{self.name}.result"
        output_path.write_text(str(count), encoding="utf-8")

        return AgentResult(
            agent_name=self.name,
            job_id=job_id,
            output_path=output_path,
            summary=f"CONSONANTS = {count}",
        )
