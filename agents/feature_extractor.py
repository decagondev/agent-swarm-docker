"""Feature-extractor agent — uses an LLM to pull out nouns + benefits."""

from pathlib import Path

from agents.base import AgentResult, BaseAgent
from core.llm.base import LLMClient
from core.registry import register_agent

_PROMPT = (
    "Extract the key features from the text below as a bulleted list of "
    "noun + benefit pairs. Be concise — at most 6 bullets, one line each."
)


@register_agent
class FeatureExtractorAgent(BaseAgent):
    name = "feature_extractor"
    description = (
        "Extract a bulleted list of key features (nouns + benefits) from the input text."
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

    def __init__(self, llm: LLMClient | None = None) -> None:
        # Lazy-resolved in run() if not injected — keeps construction cheap
        # for schema collection at registry time.
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
            summary=f"FEATURES → {len(body)} chars",
        )


def _resolve_llm() -> LLMClient:
    from core.llm import get_llm_client

    return get_llm_client()
