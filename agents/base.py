"""Abstract agent contract.

Every concrete agent the Supervisor can spawn implements `BaseAgent`. The
contract is intentionally tiny: a class-level identity + JSON-schema
parameter spec the LLM sees, and one `run()` method that reads input from
the shared volume and writes a result file.

`tool_schema()` is a classmethod so the Supervisor can collect schemas
without instantiating agents — LLM-aware agents (Epic 2) need an
`LLMClient` at construction time.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class AgentResult:
    agent_name: str
    job_id: str
    output_path: Path
    summary: str


class BaseAgent(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict[str, Any]]

    @classmethod
    def tool_schema(cls) -> ToolSchema:
        return ToolSchema(
            name=cls.name,
            description=cls.description,
            parameters=cls.parameters,
        )

    @abstractmethod
    def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult: ...
