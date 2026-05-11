"""Container entrypoint: `python -m agents.runner --agent <name> --job <id>`.

Each Swarm-spawned agent service runs this module once and exits.
"""

import argparse
import os
import sys
from pathlib import Path

import agents  # noqa: F401 — triggers @register_agent imports
from core.io.shared_volume import DEFAULT_ROOT, SharedVolume
from core.registry import REGISTRY


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agents.runner",
        description="Run a single registered agent against a job's input file.",
    )
    parser.add_argument(
        "--agent",
        required=True,
        choices=REGISTRY.names(),
        help="Name of a registered agent.",
    )
    parser.add_argument(
        "--job",
        required=True,
        help="Job id; selects <root>/input/<job>.txt and names the result file.",
    )
    parser.add_argument(
        "--data-root",
        default=os.environ.get("DATA_ROOT", str(DEFAULT_ROOT)),
        help="Shared-volume root (default: $DATA_ROOT or /app/data).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    volume = SharedVolume(Path(args.data_root))
    volume.ensure_dirs()

    input_path = volume.input_path(args.job)
    if not input_path.exists():
        print(f"runner: input file not found: {input_path}", file=sys.stderr)
        return 2

    agent_cls = REGISTRY.get(args.agent)
    result = agent_cls().run(input_path, volume.results_dir, args.job)
    print(f"{result.agent_name}: {result.summary}")
    print(f"→ {result.output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
