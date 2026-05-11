# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repo is a **live-demo asset** for an 8-minute conference talk on Docker Swarm as a runtime for parallel AI agent swarms (see `lesson-plan-prd.md` for the full PRD). The current code is the **pre-refactor baseline** — a minimal "orchestrator + workers" pattern over `docker compose`. The PRD describes a planned evolution toward a SOLID-modularized layout (`core/`, `agents/`, `docker/`) with an LLM supervisor and dynamic Docker Swarm service spawning. When making changes, check `lesson-plan-prd.md` first to see whether the work fits an already-planned epic/commit slice.

## Commands

```bash
# Build all service images
docker compose up --build -d

# Run the orchestrator with custom text (all argv after script name is joined)
docker compose run --rm orchestrator python orchestrator.py "Your paragraph here."

# Scale specific workers for parallelism (e.g. when batch mode is enabled in orchestrator.py)
docker compose up -d --scale capitalize-worker=5 --scale reverse-worker=5
```

There is no test suite, linter, or build script yet. The PRD calls for `pytest` and `make test-demo` as future work (Epic 5).

## Architecture

**File-based handoff over a shared Docker volume** — there is no message queue, no API, no LLM in the baseline. All four worker services and the orchestrator mount `./shared-data` at `/app/data`, and coordinate by reading/writing files in three subdirectories:

- `/app/data/input/` — orchestrator writes `*.txt` here
- `/app/data/results/` — workers each write `<task>_<filename>.result` here
- `/app/data/output/` — orchestrator writes `final_report.txt` and appends to `orchestrator_log.txt`

**Worker contract:** Each worker is a single `worker.py --task <name>` process that scans `/app/data/input/*.txt` **once at startup**, processes every file, writes results, and exits. Workers do not poll — they run to completion. The four task names are hardcoded in `worker.py`'s argparse `choices`: `capitalize`, `reverse`, `count_consonants`, `vowel_random`. Adding a new task requires editing both the `choices` list and the `if/elif` branches.

**Orchestrator contract:** `orchestrator.py` writes the input file, then polls `/app/data/results/` until `len(results) >= num_tasks * num_input_files` or a 60-second timeout, then aggregates. This means **workers must already be running** (`docker compose up -d`) before `docker compose run --rm orchestrator` is invoked — the orchestrator does not start them.

**Image strategy:** A single `Dockerfile` (`python:3.12-slim`, no deps) is used for all five services. The `command:` field in `docker-compose.yml` is what distinguishes a worker's task from the orchestrator. The Dockerfile's default `CMD` is `worker.py` with no `--task`, which will fail — this is intentional; every service overrides it.

## Working in this repo

- The orchestrator has a commented-out "batch mode" loop (orchestrator.py:29-31) that generates 20 files. The README references uncommenting it for scaling demos.
- `vowel_random` and `reverse` tasks write **two** files per input: a `.result` summary and a raw output file (`random_<filename>` / `reversed_<filename>`). The orchestrator's polling math only counts `.result` files, so this is fine — but be aware when adding tasks.
- The PRD's planned folder structure (`core/`, `agents/`, `docker/`) does not exist yet. Do not assume it; if asked to add an agent type today, you extend `worker.py`. If asked to start Epic 1 of the refactor, follow the commit slices in `lesson-plan-prd.md` §5.
