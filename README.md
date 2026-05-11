# agent-swarm-docker

Live-demo asset for an 8-minute talk on **Docker Swarm as a runtime for parallel LLM-driven agent swarms**. A provider-agnostic supervisor LLM treats specialized agents as **tools**, decomposes a user task, and spawns each agent as a short-lived Swarm service. Results are aggregated into a final report.

```
                 ┌──────────────┐
                 │  Supervisor  │  (LLM: OpenAI | Groq | xAI)
                 │   (1 svc)    │
                 └──────┬───────┘
                        │ docker.sock
            ┌───────────┼───────────┐
            ▼           ▼           ▼
       ┌────────┐  ┌────────┐  ┌────────┐
       │capitlz │  │reverse │  │ slogan │   ← spawned per tool call
       │ (svc)  │  │ (svc)  │  │ (svc)  │     (parallel, ephemeral)
       └───┬────┘  └───┬────┘  └───┬────┘
           └──── shared-data ──────┘   (named volume)
```

## Quickstart

```bash
# 1. Configure provider + API key
cp .env.example .env && $EDITOR .env

# 2. Bring up the swarm (idempotent: skips build if image cached)
./scripts/demo-up.sh

# 3. (optional) Watch agent services spawn in a second pane
./scripts/demo-logs.sh

# 4. Run the supervisor against your task
./scripts/demo-run.sh "Analyze this product description: 'The quick brown
fox jumps over the lazy dog while coding with Docker Swarm.'"

# 5. Tear down
./scripts/demo-down.sh
```

Expected: `docker service ls --filter label=agent-swarm.role=ephemeral` shows agent services spinning up in parallel during the run. Final report appears on stdout; per-agent outputs land in `shared-data/results/`.

## Prerequisites

- Docker Engine 24+ with Swarm support
- Python 3.12 (for local dev; not required for the demo flow above)
- An API key for **one** of: OpenAI / Groq / xAI

## Local development

```bash
# Editable install with dev tooling.
pip install -e ".[dev]"

# Unit tests (no Docker required).
pytest tests/unit

# Opt-in integration test against a real Swarm.
DOCKER_SWARM_TESTS=1 pytest tests/integration

# Lint.
ruff check .
```

Iterate without Swarm:

```bash
docker compose -f docker/compose.dev.yml build
docker compose -f docker/compose.dev.yml run --rm supervisor \
    python supervisor.py --executor threadpool "Your prompt."
```

The `threadpool` executor runs every agent in-process, which is fast for development. The `swarm` executor spawns Docker Swarm services.

## Adding a new agent

Every agent is one file with one decorator. The registry has zero name-based branching.

```python
# agents/my_agent.py
from pathlib import Path
from agents.base import AgentResult, BaseAgent
from core.registry import register_agent


@register_agent
class MyAgent(BaseAgent):
    name = "my_agent"
    description = "What the LLM sees."
    parameters = {
        "type": "object",
        "properties": {"input_ref": {"type": "string"}},
        "required": ["input_ref"],
    }

    def run(self, input_path: Path, output_dir: Path, job_id: str) -> AgentResult:
        text = input_path.read_text(encoding="utf-8")
        result = transform(text)
        out = output_dir / f"{job_id}__{self.name}.result"
        out.write_text(result, encoding="utf-8")
        return AgentResult(self.name, job_id, out, summary=f"…{len(result)} chars")
```

Then import the module from `agents/__init__.py` to trigger registration. The supervisor and LLM auto-discover it on next run.

## Switching LLM provider

Set `LLM_PROVIDER` in `.env` (one of `openai`, `groq`, `xai`), populate the matching API key, optionally set `LLM_MODEL`. No code changes.

## Offline rehearsal (bad-WiFi fallback)

When the conference WiFi melts:

```bash
python supervisor.py \
  --dry-run \
  --fixture tests/fixtures/talk_prompt_response.json \
  --job demo \
  "Your talk prompt here."
```

The supervisor replays a recorded LLM conversation. Agents still run for real — the only thing faked is the LLM round-trip.

## Repo layout

```
supervisor.py             # CLI entrypoint
agents/                   # BaseAgent + 7 concrete agents + runner
core/
  registry.py             # AgentRegistry + @register_agent
  llm/                    # LLMClient ABC + 3 adapters + scripted (dry-run)
  swarm/                  # SwarmManager + ResultWatcher
  supervisor/             # Supervisor + ThreadPool/Swarm executors
  io/shared_volume.py     # File-handoff primitive
  logging.py              # rich-based event logger
docker/                   # Dockerfile + docker-stack.yml + compose.dev.yml
scripts/                  # demo-{up,run,logs,down}.sh
tests/{unit,integration}  # pytest; integration is opt-in
```

## Security note

`docker-stack.yml` mounts `/var/run/docker.sock` into the supervisor container so it can spawn sibling services. **This is a demo artefact.** In production, use a remote Docker API with proper auth or a dedicated swarm manager — exposing the socket gives full root-equivalent control of the host.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Error: no running container for service agent-swarm_supervisor` | Run `./scripts/demo-up.sh` first. |
| `MissingAPIKeyError: OPENAI_API_KEY is not set` | Populate `.env` for the provider you chose in `LLM_PROVIDER`. |
| `docker swarm leave: node is part of an active manager` | Pass `./scripts/demo-down.sh --leave-swarm` to fully exit Swarm mode. |
| Stale agent services from a prior crashed run | `SwarmManager` reaps them automatically at startup; or run `docker service ls --filter label=agent-swarm.role=ephemeral -q \| xargs docker service rm`. |
| Image rebuilds every time | `demo-up.sh` skips build if `agent-swarm:latest` exists locally. Delete the image to force a rebuild. |
