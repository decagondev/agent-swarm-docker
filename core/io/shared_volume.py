"""Shared-volume layout primitive.

The wire format between Supervisor and agents is a Docker volume mounted at
`/app/data` in every container. This module is the one place that knows the
on-disk layout — agents and the Supervisor both go through `SharedVolume`
rather than building paths by hand.

Layout:
    <root>/input/<job_id>.txt           — Supervisor writes; agent reads.
    <root>/results/<job_id>__<agent>.result — Agent writes; Supervisor reads.
    <root>/output/                       — Final reports / logs.
"""

from pathlib import Path

DEFAULT_ROOT = Path("/app/data")


class SharedVolume:
    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def input_dir(self) -> Path:
        return self._root / "input"

    @property
    def results_dir(self) -> Path:
        return self._root / "results"

    @property
    def output_dir(self) -> Path:
        return self._root / "output"

    def ensure_dirs(self) -> None:
        for d in (self.input_dir, self.results_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)

    def input_path(self, job_id: str) -> Path:
        return self.input_dir / f"{job_id}.txt"

    def result_path(self, job_id: str, agent_name: str) -> Path:
        return self.results_dir / f"{job_id}__{agent_name}.result"

    def write_input(self, job_id: str, text: str) -> Path:
        self.ensure_dirs()
        path = self.input_path(job_id)
        path.write_text(text, encoding="utf-8")
        return path
