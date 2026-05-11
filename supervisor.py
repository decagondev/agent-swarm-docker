"""CLI entrypoint for the LLM-driven Supervisor.

Usage:
    LLM_PROVIDER=groq GROQ_API_KEY=... python supervisor.py "Analyze: ..."

Loads .env from the working directory (host) or /app/.env (container) if
present. Provider is chosen via the `LLM_PROVIDER` env var; see .env.example.
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

import agents  # noqa: F401 — triggers @register_agent imports
from core.io.shared_volume import DEFAULT_ROOT, SharedVolume
from core.llm import get_llm_client
from core.logging import SwarmEventLogger
from core.registry import REGISTRY
from core.supervisor import (
    AgentExecutor,
    Supervisor,
    SwarmAgentExecutor,
    ThreadPoolAgentExecutor,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python supervisor.py",
        description="Run the LLM-driven agent-swarm Supervisor on a user prompt.",
    )
    parser.add_argument(
        "prompt",
        nargs="+",
        help="The user task. Multiple words are joined with spaces.",
    )
    parser.add_argument(
        "--job",
        default=None,
        help="Optional job id. Auto-generated when omitted.",
    )
    parser.add_argument(
        "--data-root",
        default=os.environ.get("DATA_ROOT", str(DEFAULT_ROOT)),
        help="Shared-volume root (default: $DATA_ROOT or /app/data).",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Override LLM_PROVIDER (openai | groq | xai).",
    )
    parser.add_argument(
        "--executor",
        choices=("threadpool", "swarm"),
        default=os.environ.get("AGENT_SWARM_EXECUTOR", "threadpool"),
        help=(
            "How to run tool calls. 'threadpool' (default) runs agents in-process; "
            "'swarm' spawns one ephemeral Docker Swarm service per call."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress spawn/cleanup/iter events on stderr.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _build_parser().parse_args(argv)
    prompt = " ".join(args.prompt)

    logger = SwarmEventLogger.silent() if args.quiet else SwarmEventLogger.default()
    volume = SharedVolume(args.data_root)
    volume.ensure_dirs()
    llm = get_llm_client(args.provider)
    executor = _build_executor(args.executor, volume, llm, logger)
    supervisor = Supervisor(
        llm=llm,
        registry=REGISTRY,
        executor=executor,
        volume=volume,
        logger=logger,
    )

    final = supervisor.run(prompt, job_id=args.job)
    print(final)
    return 0


def _build_executor(
    kind: str, volume: SharedVolume, llm, logger: SwarmEventLogger
) -> AgentExecutor:
    if kind == "threadpool":
        return ThreadPoolAgentExecutor(REGISTRY, volume, llm=llm)
    if kind == "swarm":
        from core.swarm import ResultWatcher, SwarmManager

        image = os.environ.get("AGENT_SWARM_IMAGE", "agent-swarm:latest")
        shared_volume = os.environ.get("AGENT_SWARM_VOLUME", "agent-swarm_shared-data")
        swarm = SwarmManager(image=image, shared_volume=shared_volume, logger=logger)
        watcher = ResultWatcher(volume.results_dir)
        return SwarmAgentExecutor(REGISTRY, volume, swarm, watcher, logger=logger)
    raise ValueError(f"Unknown executor: {kind!r}")


if __name__ == "__main__":
    sys.exit(main())
