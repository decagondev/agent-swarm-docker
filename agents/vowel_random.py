"""Vowel-random agent — emits 2× the vowel count in random ASCII characters."""

import random
import string
from pathlib import Path

from agents.base import AgentResult, BaseAgent
from core.registry import register_agent

_VOWELS = frozenset("aeiouAEIOU")
_ALPHABET = string.ascii_letters + string.digits


def count_vowels(text: str) -> int:
    return sum(1 for c in text if c.isalpha() and c in _VOWELS)


@register_agent
class VowelRandomAgent(BaseAgent):
    name = "vowel_random"
    description = (
        "Count vowels in the input and emit a random ASCII string of double that length."
    )
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

    def __init__(self, rng: random.Random | None = None) -> None:
        # RNG is injectable so tests can pin a seed; default constructs a
        # fresh entropy-seeded Random per instance (no shared mutable default).
        self._rng = rng if rng is not None else random.Random()

    def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
        text = input_path.read_text(encoding="utf-8")
        vowel_count = count_vowels(text)
        num_chars = vowel_count * 2
        random_str = "".join(self._rng.choices(_ALPHABET, k=num_chars))

        output_path = output_dir / f"{job_id}__{self.name}.result"
        output_path.write_text(random_str, encoding="utf-8")

        return AgentResult(
            agent_name=self.name,
            job_id=job_id,
            output_path=output_path,
            summary=f"VOWELS = {vowel_count} → {num_chars} random chars generated",
        )
