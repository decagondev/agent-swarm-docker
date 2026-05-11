"""File-based wait primitive for Swarm-spawned agent runs.

A spawned agent service writes its result to
    <results_dir>/<job_id>__<agent>.result
on the shared volume. The supervisor uses `ResultWatcher` to block until that
file appears (or until a timeout elapses) — file-based signalling means the
supervisor doesn't have to poll the Docker API for every tool call.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path


class ResultWatcherTimeoutError(TimeoutError):
    """Raised when an expected result file did not appear in time."""


class ResultWatcher:
    def __init__(self, results_dir: Path, poll_interval_s: float = 0.2) -> None:
        self._results_dir = Path(results_dir)
        self._poll_interval = poll_interval_s

    def expected_path(self, job_id: str, agent_name: str) -> Path:
        return self._results_dir / f"{job_id}__{agent_name}.result"

    def wait_for(self, job_id: str, agent_name: str, timeout_s: float = 60.0) -> Path:
        target = self.expected_path(job_id, agent_name)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if target.exists():
                return target
            time.sleep(self._poll_interval)
        raise ResultWatcherTimeoutError(
            f"Result file {target.name} did not appear within {timeout_s}s"
        )

    def wait_for_many(
        self,
        job_id: str,
        agent_names: Iterable[str],
        timeout_s: float = 60.0,
    ) -> dict[str, Path]:
        """Block until *all* named result files exist; return name → path map."""
        agents = list(agent_names)
        pending = {name: self.expected_path(job_id, name) for name in agents}
        found: dict[str, Path] = {}
        deadline = time.monotonic() + timeout_s
        while pending and time.monotonic() < deadline:
            for name, path in list(pending.items()):
                if path.exists():
                    found[name] = path
                    del pending[name]
            if pending:
                time.sleep(self._poll_interval)
        if pending:
            missing = ", ".join(sorted(pending))
            raise ResultWatcherTimeoutError(
                f"Result files missing after {timeout_s}s: {missing}"
            )
        return found
