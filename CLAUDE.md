# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repo is a **live-demo asset** for an 8-minute conference talk on Docker Swarm as a runtime for parallel AI agent swarms. The end state is a SOLID-modular Python package with a provider-agnostic LLM supervisor that uses registered agents as tools and dynamically spawns Docker Swarm services. See `lesson-plan-prd.md` for the original PRD, `docs/TALK.md` for the 8-minute talk script, `docs/slides.html` for the slides, and `README.md` for the clone-and-run path.

## Commands

```bash
# Demo path (Swarm executor).
./scripts/demo-up.sh                       # swarm init + build (cached) + stack deploy
./scripts/demo-run.sh "Your task"          # docker exec into supervisor service
./scripts/demo-logs.sh                     # watch agent services spawn/exit
./scripts/demo-down.sh                     # stack rm + volume rm

# Dev path (in-process threadpool — faster iteration).
docker compose -f docker/compose.dev.yml build
docker compose -f docker/compose.dev.yml run --rm supervisor \
    python supervisor.py --executor threadpool "..."

# Local Python — canonical entrypoints via Makefile.
make install                               # pip install -e ".[dev]" + requirements.txt
make test                                  # pytest tests/unit -v (no Docker)
make test-demo                             # DOCKER_SWARM_TESTS=1 pytest tests/integration -v
make test-all                              # both
make lint                                  # ruff check .
make format                                # ruff check --fix + ruff format
make image                                 # docker build -f docker/Dockerfile -t agent-swarm:latest .

# Single test (file / node id).
pytest tests/unit/test_registry.py -v
pytest tests/unit/test_registry.py::test_registers_decorator -v
pytest -k swarm_executor                   # by keyword across the suite

# Offline rehearsal (no LLM network).
python supervisor.py --dry-run --fixture tests/fixtures/talk_prompt_response.json \
    --job demo --data-root /tmp/demo "..."
```

CI runs `make lint test` on PRs via `.github/workflows/ci.yml`. The Makefile + `scripts/*.sh` assume POSIX tools (`find`, `rm`); on Windows, run them through WSL or inside the Docker dev container.

## Architecture

**Composition root** is `supervisor.py` (root entrypoint). It wires `get_llm_client()` → `Supervisor(llm, registry, executor, volume, logger)` and runs a turn-based LLM loop until the model returns a final answer (no more tool calls).

**SOLID boundaries:**
- `agents/base.py` — `BaseAgent` ABC, `ToolSchema`/`AgentResult` frozen dataclasses. `tool_schema()` is `@classmethod` so the registry can collect schemas without instantiating LLM-aware agents.
- `core/registry.py` — `AgentRegistry` + `@register_agent` decorator. Open/Closed: zero name-based branching. Adding an agent = one file + decorator + side-effect import from `agents/__init__.py`.
- `core/llm/` — `LLMClient` ABC (Dependency Inversion). `_OpenAICompatibleClient` shared base; `OpenAIClient`/`GroqClient`/`XAIClient` are 10-LOC subclasses differing only in `BASE_URL` + `API_KEY_ENV`. Factory `get_llm_client(provider)` lazy-imports the concrete class so `core.llm` stays cheap to import. `ScriptedLLMClient` replays JSON fixtures for offline rehearsal.
- `core/swarm/` — `SwarmManager` is Protocol-typed against `_DockerClientProtocol` so tests use `FakeDockerClient` (in `tests/conftest.py`) and production uses `docker.from_env()`. `ServiceSpec` is a pure dataclass with `to_create_kwargs()`. `ResultWatcher` polls the shared volume for `<job>__<agent>.result` files.
- `core/supervisor/` — `Supervisor` + two executors (`ThreadPoolAgentExecutor`, `SwarmAgentExecutor`) implementing the same `AgentExecutor` Protocol. Epic-3's Swarm swap was a single file change because of this. Aggregator helpers build the OpenAI tool-call message turn shape.

**Wire format**: File-based handoff via a shared volume (`/app/data`). The Supervisor writes input to `input/<job>.txt`; each agent writes its result to `results/<job>__<agent>.result`. `SwarmAgentExecutor`'s `AgentResult.summary` is the file content (clipped to 800 chars) since Swarm-spawned agents can't return Python objects.

**LLM injection into agents**: `ThreadPoolAgentExecutor` uses `inspect.signature` to detect whether an agent's `__init__` accepts `llm=` — simple agents (capitalize/reverse/etc.) ignore it; LLM-aware agents (feature_extractor/slogan_generator/translator) receive a shared client. Swarm-spawned agents construct their own client lazily via `get_llm_client()` from env.

**Per-agent container entrypoint**: `agents/runner.py` is what each Swarm-spawned service actually executes. It receives `--agent <name>` + `--job <id>`, looks the agent class up in the registry, runs it against the shared-volume input file, and writes the `.result` artifact that `ResultWatcher` is polling for. Adding a new agent does not require touching `runner.py`.

**Logging**: `core/logging.py` `SwarmEventLogger` is rich-based. Final-answer text goes to stdout; spawn/cleanup/iter events go to stderr — pipeline-safe (`supervisor.py ... | tee result.txt` works).

## Working in this repo

- **Agent ↔ LLM coupling**: The `parameters` JSON schema on each `BaseAgent` is what the LLM sees. The agent's `run()` does NOT receive those parameters — it just operates on the job's input file. Every agent's schema currently requires `input_ref` for consistency, but the value is informational only.
- **Registry side-effect imports**: Concrete agents are activated by being imported in `agents/__init__.py`. Forgetting that line means the agent exists but the LLM never sees it.
- **Two executors, one Protocol**: When changing supervisor behavior, make sure both `ThreadPoolAgentExecutor` and `SwarmAgentExecutor` keep behaving identically from the Supervisor's perspective — they're the substitutability test.
- **Stale-service reaper**: `SwarmManager` reaps `agent-swarm.role=ephemeral` services on construction by default. If you add a new long-lived role, label it differently (the supervisor itself uses `role=supervisor`).
- **Talk fixture limit**: `tests/fixtures/talk_prompt_response.json` deliberately omits LLM-aware agents (feature_extractor, slogan_generator, translator) because they'd recursively consume responses from the same `ScriptedLLMClient`. If you extend the fixture with those agents, add per-agent responses for each LLM call.
- **`shared-data/` is host-side, root-owned**: Docker writes there as root. Cleanup uses an `alpine` container: `docker run --rm -v "$(pwd)/shared-data:/data" alpine sh -c "rm -rf /data/*"`.
- **Docker socket security**: `docker/docker-stack.yml` mounts `/var/run/docker.sock` so the supervisor can spawn sibling services. This is a demo-only pattern; README calls it out.
