"""Rich-based event logger for swarm spawn / wait / cleanup events.

Used by `SwarmManager`, `SwarmAgentExecutor`, and `Supervisor`. A `None`
console silences output — convenient for tests and quiet CLI invocations.
The default console writes to stderr so logging doesn't interleave with the
final-answer text the CLI prints to stdout.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.text import Text


class SwarmEventLogger:
    def __init__(self, console: Console | None = None) -> None:
        self._console = console

    @classmethod
    def default(cls) -> SwarmEventLogger:
        return cls(Console(file=sys.stderr, highlight=False))

    @classmethod
    def silent(cls) -> SwarmEventLogger:
        return cls(None)

    # ----- Swarm lifecycle events -----------------------------------------

    def spawn(self, agent: str, job_id: str, service_id: str) -> None:
        self._emit("SPAWN", "cyan", agent, service=service_id[:12], job=job_id)

    def complete(self, agent: str, job_id: str, elapsed_s: float) -> None:
        self._emit("DONE", "green", agent, job=job_id, elapsed=f"{elapsed_s:.2f}s")

    def cleanup(self, agent: str, job_id: str, service_id: str) -> None:
        self._emit("CLEAN", "dim cyan", agent, service=service_id[:12])

    def reap(self, count: int) -> None:
        if count > 0:
            self._emit("REAP", "yellow", f"{count} stale services removed")

    # ----- Supervisor loop events -----------------------------------------

    def llm_round(self, iteration: int, n_tool_calls: int) -> None:
        self._emit("LLM", "magenta", f"iter {iteration}", tools=n_tool_calls)

    def llm_final(self, iteration: int, length: int) -> None:
        self._emit("LLM", "bold magenta", f"iter {iteration}: final answer", chars=length)

    def warn(self, message: str) -> None:
        self._emit("WARN", "bold yellow", message)

    # ----- internals ------------------------------------------------------

    def _emit(self, label: str, color: str, subject: str, **kvs: Any) -> None:
        if self._console is None:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        line = Text()
        line.append(f"[{ts}] ", style="dim")
        line.append(f"{label:<6}", style=f"bold {color}")
        line.append(f" {subject}", style="bold")
        if kvs:
            kv = "  ".join(f"{k}={v}" for k, v in kvs.items())
            line.append(f"   {kv}", style="dim")
        self._console.print(line)
