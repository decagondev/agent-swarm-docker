# Demo Run Report

End-to-end execution of the agent-swarm demo on Windows 11 + Docker Desktop, performed 2026-05-13.

- **LLM provider**: Groq (`llama-3.3-70b-versatile`) — temporary lecture key.
- **Host**: Windows 11 Pro, Docker Engine 29.3.1 (Docker Desktop, Linux engine), Docker Swarm initialized fresh during this run.
- **Shell**: Git Bash on Windows for `scripts/*.sh`; PowerShell elsewhere.

## TL;DR

The demo works end-to-end. The supervisor decomposed a single prompt into three parallel agent tool-calls, Swarm spawned a service per tool call, agents wrote their results to a shared volume, the supervisor aggregated them into a final answer in a second LLM turn, and ephemeral services were reaped. Total supervisor wall time: ~4 s.

Two real findings:

1. **`demo-down.sh` silently fails to remove the shared volume** when the supervisor task container outlives its service for a few seconds (race condition on Docker Desktop Windows). Output still reports success. Reproducible.
2. **Clock skew** between host (local TZ) and supervisor container (UTC) makes correlating monitor timestamps with supervisor logs awkward — cosmetic, not functional.

Everything else worked as designed.

---

## 1. `demo-up.sh` — cluster + image + stack

**Command**

```bash
bash ./scripts/demo-up.sh
```

**What happened**

1. `docker swarm init` — host was not yet a swarm member; initialized as Leader on `docker-desktop` node.
2. `docker build -f docker/Dockerfile -t agent-swarm:latest .` — cold build. Pulled `python:3.12-slim` base (~30 MB layer download took ~37 s on this connection), installed pip deps in ~15 s. Total build ~62 s. Subsequent runs would skip via the `docker image inspect` short-circuit at script line 30.
3. `docker stack deploy -c docker/docker-stack.yml agent-swarm` — created overlay network `agent-swarm_agent-swarm-net` and service `agent-swarm_supervisor`.

**Verification**

```text
NAME                     REPLICAS   IMAGE                CURRENT STATE
agent-swarm_supervisor   1/1        agent-swarm:latest   Running
```

**Right**: idempotent swarm init, env interpolation from `.env` worked (Groq creds reached the supervisor), `.gitignore` correctly kept `.env` out of the image (Dockerfile `COPY . /app` would otherwise grab it — `.dockerignore` covers it).

**Wrong**: nothing.

**Notes**: All `scripts/*.sh` files are checked in with **CRLF line terminators**. Git for Windows' `bash` tolerated this for these scripts (they're plain enough), but `set -euo pipefail` plus more complex constructs sometimes break under CRLF. Consider committing a `.gitattributes` with `*.sh text eol=lf` to prevent future breakage.

---

## 2. `demo-run.sh` — the actual demo

**Command**

```bash
bash ./scripts/demo-run.sh \
  "Analyze this product description and produce a short marketing brief: 'The quick brown fox jumps over the lazy dog while coding with Docker Swarm.'"
```

**Supervisor output (stderr → events; stdout → final answer)**

```
→ exec into cf6ddd359d39 (service agent-swarm_supervisor)
[13:12:01] LLM    iter 0   tools=3
[13:12:01] SPAWN  feature_extractor   service=q3y0jjl0oaca  job=job-d3c1f146
[13:12:01] SPAWN  count_consonants   service=k5163o8goksl  job=job-d3c1f146
[13:12:01] SPAWN  slogan_generator   service=u8h33qcskpj0  job=job-d3c1f146
[13:12:02] DONE   count_consonants   job=job-d3c1f146  elapsed=1.42s
[13:12:02] CLEAN  count_consonants   service=k5163o8goksl
[13:12:04] DONE   slogan_generator   job=job-d3c1f146  elapsed=2.82s
[13:12:04] CLEAN  slogan_generator   service=u8h33qcskpj0
[13:12:04] DONE   feature_extractor   job=job-d3c1f146  elapsed=3.02s
[13:12:04] CLEAN  feature_extractor   service=q3y0jjl0oaca
[13:12:05] LLM    iter 1: final answer   chars=633
```

**Final answer (stdout)**

> The product description has been analyzed and key features have been extracted as noun + benefit pairs: 'Container - Simplified deployment', 'Orchestration - Efficient management', 'Docker Swarm - Enhanced scalability', 'Coding - Improved productivity', 'Deployment - Faster time-to-market', 'Management - Reduced complexity'. The slogan generator has produced the following marketing slogans: 'Unleash the Power of Agile Coding', 'Code Smarter Not Harder with Docker Swarm', 'Transform Your Development with Lightning Speed'. The consonant count is 80. These results can be used to create a short marketing brief for the product.

**Live ephemeral service transitions** (captured by a 1 s poller on `docker service ls --filter label=agent-swarm.role=ephemeral`):

```
[14:12:02] ephemeral services: agent-swarm-count_consonants-job-d3c1f146-24ff94 0/1
                              | agent-swarm-feature_extractor-job-d3c1f146-04f9e7 0/1
                              | agent-swarm-slogan_generator-job-d3c1f146-090305 0/1
[14:12:03] ephemeral services: agent-swarm-feature_extractor-…-04f9e7 1/1
                              | agent-swarm-slogan_generator-…-090305 1/1
[14:12:05] ephemeral services: (none)
```

`count_consonants` finished and was reaped before the next poll tick, which is why the second snapshot only shows two services. This is the parallel-spawn-then-clean behavior the talk is designed to show.

**Shared-volume artifacts** (read from inside the supervisor):

| Path | Bytes / content |
|---|---|
| `/app/data/input/job-d3c1f146.txt` | Original prompt text |
| `/app/data/results/job-d3c1f146__count_consonants.result` | `80` |
| `/app/data/results/job-d3c1f146__feature_extractor.result` | 6-line markdown bullet list of noun-benefit pairs |
| `/app/data/results/job-d3c1f146__slogan_generator.result` | 3 slogans, one per line |

All three result files were written under the deterministic `<job>__<agent>.result` naming, confirming `ResultWatcher` polling works.

**Right**:
- 3 tool calls fired in parallel from a single LLM turn (`iter 0   tools=3`).
- Each spawn = real Swarm service: confirmed via the labels-filtered service list.
- Cleanup ran immediately on `DONE` — no orphans.
- `SwarmAgentExecutor.AgentResult.summary` came back populated for all three agents (the final-answer text references all three by content).
- LLM-aware agents (`feature_extractor`, `slogan_generator`) successfully constructed their own Groq client lazily from env (`get_llm_client()` from inside ephemeral services).
- The simple, non-LLM agent (`count_consonants`) ran identically — substitutability holds.
- Second LLM turn returned a final answer with no further tool calls, ending the supervisor loop cleanly.

**Wrong**: nothing in this step.

**Notes**:
- The supervisor's event timestamps are in **UTC** (`13:12:xx`), while the host poller logged in **local time** (`14:12:xx`). One-hour offset on this box (BST or CEST equivalent). It's harmless but it makes it look like the host poller saw services *after* the supervisor said they were done. They're the same instant.
- `LLM    iter 1: final answer   chars=633` — the alignment in the log line has two spaces after `LLM` and one space before `iter 1`. Probably padded for fixed-width log levels. Cosmetic.

---

## 3. `demo-down.sh` — the actual problem

**Command**

```bash
bash ./scripts/demo-down.sh
```

**Output**

```
→ docker stack rm agent-swarm
→ waiting for services to fully tear down
→ removing volume agent-swarm_shared-data (if present)
✅ Teardown complete.
```

**Post-teardown reality**

```text
docker service ls --filter label=agent-swarm.role  →  (empty)
docker volume ls --filter name=agent-swarm        →  agent-swarm_shared-data   ← STILL THERE
docker info → Swarm: active (expected; --leave-swarm not passed)
```

The script reports success but the volume is leaked.

**Root cause**

`demo-down.sh` lines 13–19:

```bash
for _ in {1..30}; do
  remaining="$(docker service ls --filter "label=com.docker.stack.namespace=${STACK}" -q | wc -l)"
  if [[ "$remaining" -eq 0 ]]; then
    break
  fi
  sleep 1
done
```

This waits until the **service** is gone, not until the **task container** is gone. On Docker Desktop Windows, the supervisor service disappeared from `docker service ls` while its underlying container (`cf6ddd359d39…`) was still `Up`. The next line tries to remove the volume:

```bash
docker volume rm "${STACK}_shared-data" 2>/dev/null || true
```

…which fails with:

```
Error response from daemon: remove agent-swarm_shared-data:
  volume is in use - [cf6ddd359d39fe206a4099bb893ce74bf3c6048701cd29b0e84a273ccee2508b]
```

…and the failure is **silenced by `2>/dev/null || true`**, so the user gets the green checkmark.

**Reproducibility**: hit it on the first try. A retry one second later succeeded. Looks deterministic on this host but probably races more often on faster boxes (i.e. might not reproduce on Linux). On Linux Swarm the script likely works because container teardown is essentially synchronous; Docker Desktop's VM adds latency.

**Suggested fix** (not applied; flagging for the user)

Replace the service-count wait with a container-count wait, or at minimum surface the `volume rm` failure. Sketch:

```bash
for _ in {1..30}; do
  svcs="$(docker service ls --filter "label=com.docker.stack.namespace=${STACK}" -q | wc -l)"
  ctrs="$(docker ps -aq --filter "label=com.docker.stack.namespace=${STACK}" | wc -l)"
  if [[ "$svcs" -eq 0 && "$ctrs" -eq 0 ]]; then break; fi
  sleep 1
done

if ! docker volume rm "${STACK}_shared-data" 2>/dev/null; then
  echo "⚠️  volume ${STACK}_shared-data still in use; leaving in place" >&2
fi
```

The README's troubleshooting table mentions "stale agent services from a prior crashed run" but not "stale volume after clean teardown."

---

## 4. Other observations

### Things that worked particularly well

- **Provider switch was zero-code**: just `LLM_PROVIDER=groq` + `GROQ_API_KEY=…` in `.env`. The OpenAI-compatible `_OpenAICompatibleClient` base + Groq adapter handled it.
- **`.dockerignore` did its job**: `.env` not baked into the image; secrets only delivered via `docker-stack.yml` env interpolation at deploy time.
- **`set -a; source .env; set +a`** in `demo-up.sh` (line 12–16) is the right way to expose `.env` vars to `docker stack deploy`'s interpolation. Worth keeping in mind: `docker stack deploy` does *not* read `.env` automatically the way `docker compose` does.
- **Idempotent swarm init**: the `if [[ … != "active" ]]` check at line 22 of `demo-up.sh` makes re-running the script safe.

### Things to keep an eye on for the talk

- **Cold build is ~60 s**. The script skips build if `agent-swarm:latest` exists locally, so do a pre-talk `demo-up.sh` once to prime the image cache.
- **Conference WiFi** would matter for the LLM call (each agent runs Groq too), not for the Docker pulls — those would already be cached. The `--dry-run --fixture` fallback documented in `CLAUDE.md` covers that.
- **Service names are long**: `agent-swarm-feature_extractor-job-d3c1f146-04f9e7`. They wrap awkwardly in narrow terminals. If you want them to look tidier on stage, consider truncating the job-id segment when generating the service name.

### Pre-existing-CRLF risk

`scripts/*.sh` are all CRLF. If anyone clones on Windows without `core.autocrlf=input` and tries to run via WSL bash or the dev container's bash, they'll get `bash: ./scripts/demo-up.sh: /usr/bin/env: 'bash\r': No such file or directory`. A one-line `.gitattributes` would inoculate against this.

---

## Outcome

| Step | Result | Time |
|---|---|---|
| `demo-up.sh` | ✅ Swarm init + cold image build + stack deploy | ~80 s |
| Supervisor startup (1/1 replica) | ✅ Healthy | ~5 s |
| `demo-run.sh` end-to-end | ✅ 3 parallel agents, final answer | ~4 s |
| Ephemeral cleanup | ✅ All 3 services reaped automatically | (during run) |
| `demo-down.sh` | ⚠️ Reports success but leaks `agent-swarm_shared-data` volume | ~6 s |
| Manual `docker volume rm` retry | ✅ Worked after container fully exited | ~1 s |

Net: the demo path is solid for a live talk. The `demo-down.sh` volume leak is a real bug but does not affect any user-facing demo behavior — it only shows up if you inspect `docker volume ls` after teardown.
