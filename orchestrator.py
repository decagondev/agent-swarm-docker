"""Legacy orchestrator — dependency-inverted onto the new agent registry.

Bridges the original demo CLI (`python orchestrator.py "paragraph"`) to the
new architecture: drops the hardcoded task list, drives a one-subprocess-
per-agent fan-out via `python -m agents.runner`, and aggregates result files
written by each agent into a single `final_report.txt`.

This module is the closing piece of Epic 1; Epic 2 replaces it with an
LLM-driven `supervisor.py`.
"""

import subprocess
import sys
from datetime import datetime

import agents  # noqa: F401 — triggers @register_agent imports
from core.io.shared_volume import SharedVolume
from core.registry import REGISTRY

DEFAULT_PARAGRAPH = (
    "The quick brown fox jumps over the lazy dog. "
    "This is a test paragraph for the agent swarm."
)
JOB_ID = "initial_paragraph"


def main() -> int:
    paragraph = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_PARAGRAPH
    if len(sys.argv) < 2:
        print("⚠️  No paragraph provided — using demo text.")

    volume = SharedVolume()
    volume.ensure_dirs()
    input_path = volume.write_input(JOB_ID, paragraph)
    print(f"📝 Orchestrator created initial file: {input_path}")

    agent_names = REGISTRY.names()
    print(f"⏳ Fanning out to {len(agent_names)} agents: {', '.join(agent_names)}")
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "agents.runner", "--agent", name, "--job", JOB_ID],
        )
        for name in agent_names
    ]
    exit_codes = [p.wait() for p in procs]

    timestamp = datetime.now().isoformat()
    report_path = volume.output_dir / "final_report.txt"
    log_path = volume.output_dir / "orchestrator_log.txt"

    with report_path.open("w", encoding="utf-8") as report:
        report.write(f"FINAL REPORT — Generated at {timestamp}\n")
        report.write(f"Agents run: {len(agent_names)}\n\n")
        for name, code in zip(agent_names, exit_codes, strict=True):
            result_path = volume.result_path(JOB_ID, name)
            report.write(f"--- {name} (exit={code}) ---\n")
            if result_path.exists():
                report.write(result_path.read_text(encoding="utf-8"))
            else:
                report.write("(no result file)")
            report.write("\n\n")

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"[{timestamp}] orchestrator finished; exit_codes={exit_codes}\n")

    print("✅ Orchestrator finished!")
    print(f"📁 Final report  → {report_path}")
    print(f"📋 Master log    → {log_path}")
    print(f"📂 Raw results   → {volume.results_dir}")
    return 0 if all(c == 0 for c in exit_codes) else 1


if __name__ == "__main__":
    sys.exit(main())
