# TALK.md — 8-minute live demo script

Goal: leave the audience with a working mental model of *"LLM → Docker Swarm → parallel agents"* and a repo they can clone and run in 2 commands.

Target audience: AI-first developers who know LLMs / LangChain but are new to Docker / Swarm.

## Pre-talk checklist (run T-5 minutes)

```bash
# 1. Stage laptop has a fresh Docker daemon.
docker info --format '{{.ServerVersion}}'

# 2. Swarm is initialised. (Idempotent inside demo-up.sh, but pre-warm it.)
docker swarm init || echo "(already)"

# 3. Image is pre-built so the audience doesn't watch pip install.
docker build -f docker/Dockerfile -t agent-swarm:latest .

# 4. .env is populated. Sanity-check the API key reaches a model.
python -c "from core.llm import get_llm_client; print(get_llm_client().chat('say ok', [{'role':'user','content':'hi'}], []).text)"

# 5. Two terminals + Slack-up the prompt text. (Keep the demo prompt copy-pasteable.)
```

Open two terminal panes side-by-side: **left** = supervisor invocations; **right** = `./scripts/demo-logs.sh` running.

## The demo prompt

Copy-paste this into the supervisor invocation:

> Analyze this product description for our new "Docker Agent" tool:
> "The quick brown fox jumps over the lazy dog while coding with Docker Swarm."
> Break it down and do the following in parallel:
> 1. Extract key features (nouns + benefits).
> 2. Generate 3 catchy marketing slogans.
> 3. Translate ONE slogan to French.
> 4. Count consonants & generate a "random vowel-inspired" string.
> 5. Reverse the original description for a "backwards compatibility" joke.
> Return a polished final report.

## Minute-by-minute

### 0:00 — 0:45 · Hook (slide, no terminal)

"Every agent demo you've seen wires up tools with `if/elif`. Today I'll show you how to treat *agents themselves* as the tools, and let Docker Swarm scale them for free."

Show repo URL + the 4-command quickstart from the README. Promise the audience they'll run this themselves in 8 minutes.

### 0:45 — 1:30 · Why Docker Swarm, not Kubernetes (slide)

One slide. Three bullets:
- Single-node demo = `docker swarm init`. No control plane, no kubeconfig.
- Services are just `docker.from_env().services.create(...)` from the SDK.
- Same primitives scale horizontally — production-grade ergonomics without K8s tax.

### 1:30 — 2:30 · `demo-up.sh` (terminal, left pane)

```bash
./scripts/demo-up.sh
```

While it runs, narrate:
- "First command does three things: `docker swarm init`, build the image, deploy the stack."
- "The stack file declares ONE service — the supervisor. The agents aren't here. We'll spawn them dynamically."

Show `docker/docker-stack.yml` briefly. Highlight the `/var/run/docker.sock` mount and call out: **"demo only — root-equivalent access."**

### 2:30 — 3:30 · `demo-logs.sh` + the prompt (right pane)

```bash
./scripts/demo-logs.sh        # in the right pane
```

Show that only the supervisor service is running.

Now in the left pane:

```bash
./scripts/demo-run.sh "$(cat demo-prompt.txt)"
```

While it loads, narrate the architecture diagram from the README.

### 3:30 — 5:00 · The fan-out (THE MONEY SHOT)

When the LLM emits tool calls, the right pane lights up with 4–5 new services appearing in `docker service ls`. They each run a one-shot agent and exit.

Read out the spawn events as they happen on the left pane (rich logger):

```
[12:34:56] SPAWN  capitalize         service=svc-abcd1234  job=demo
[12:34:56] SPAWN  reverse            service=svc-abcd2345  job=demo
[12:34:56] SPAWN  feature_extractor  service=svc-abcd3456  job=demo
[12:34:56] SPAWN  slogan_generator   service=svc-abcd4567  job=demo
[12:34:56] SPAWN  translator         service=svc-abcd5678  job=demo
```

Drive the point: "Five services. They started in the same wall-clock millisecond because the LLM emitted them as parallel tool calls. The supervisor is a thin loop — the LLM does the planning."

### 5:00 — 6:00 · The final report (left pane)

DONE events stream in. The final report prints. Read 1-2 highlights — the French slogan and the reversed text are crowd-pleasers.

Open `shared-data/results/` in the file explorer or `ls`:

```bash
docker run --rm -v agent-swarm_shared-data:/data alpine ls /data/results
```

"Each agent wrote a file. The supervisor read them back as tool results and aggregated."

### 6:00 — 7:00 · "Add an agent in 15 lines" (code, slide)

Show the snippet from the README. Make the case that the registry has zero name-based branching — adding an agent is one file + one decorator.

Optional: live-add a `pig_latin` agent and re-run the prompt. If you have time. If not, skip — the README has the same example.

### 7:00 — 7:30 · `demo-down.sh` (tear-down)

```bash
./scripts/demo-down.sh
```

`docker service ls` empties. Drive home: "Ephemeral, cleaned up. No leftover state. A real production pattern."

### 7:30 — 8:00 · Wrap (slide)

Two takeaways:
1. **SOLID + LLM tool-use makes agent swarms boring**: `BaseAgent` ABC + `@register_agent` + `LLMClient` ABC = composable without spaghetti.
2. **Docker Swarm is the right runtime when K8s is overkill**: same dynamic-spawn pattern, ~150 LOC of Python, no extra control plane.

Repo URL on the slide. Promise that `./scripts/demo-up.sh` works on their laptop right now.

## Fallback playbook

### Stage WiFi is broken

```bash
python supervisor.py \
  --dry-run \
  --fixture tests/fixtures/talk_prompt_response.json \
  --job demo \
  --executor swarm \
  "$(cat demo-prompt.txt)"
```

The LLM round-trip is replayed from the fixture; agents still run via real Swarm services. Visually identical fan-out. Acknowledge it on stage: *"Replayed conversation — same code path, no network."*

### Swarm refuses to start (e.g. macOS Docker Desktop hiccup)

Drop to the in-process executor — the talk is about the LLM-as-orchestrator pattern, not Swarm specifically:

```bash
docker compose -f docker/compose.dev.yml build
docker compose -f docker/compose.dev.yml run --rm supervisor \
    python supervisor.py --executor threadpool "$(cat demo-prompt.txt)"
```

The spawn events still print; the visual is less dramatic but the architecture story holds.

### A specific agent fails on stage

The supervisor surfaces the error in the next LLM tool result and continues. Don't apologize — narrate it: *"Real systems are messy; the supervisor handed the failure back to the LLM and it kept going."*

### LLM provider rate-limits mid-demo

Switch providers with one flag:

```bash
./scripts/demo-run.sh --provider groq "$(cat demo-prompt.txt)"
```

Pre-populate `GROQ_API_KEY` in `.env` before the talk so this is one keystroke.

## Q&A primer

| Likely question | Short answer |
|---|---|
| Why not LangChain? | We use the OpenAI tool-call protocol directly. LangChain would add a layer; our `LLMClient` ABC + `BaseAgent` is the whole abstraction. |
| Why not Kubernetes? | Same `services.create` primitive, no control plane to operate. Swarm is the right level for a demo and small production workloads. |
| Does this scale? | Yes — `docker service scale` works on the supervisor for inbound concurrency; each tool call spawns its own short-lived service. Limit is whatever the Swarm cluster size is. |
| Security? | Demo mounts `/var/run/docker.sock` — that's a smell. In production, use a remote Docker API with mTLS or a queue + dedicated spawner. |
| Cost? | One LLM call per Supervisor iteration (typically 2). Each agent that needs an LLM (feature_extractor, slogan_generator, translator) makes one focused call. Cheaper than chain-of-thought reasoning loops. |
| Why file-based handoff? | Zero deps. The shared volume *is* the message queue. Could be Redis or NATS in production. |
| Source? | Repo URL is on the title slide. `git clone`, `./scripts/demo-up.sh`, you're live. |

## Cue card

```
0:00  Hook
0:45  Why Swarm
1:30  demo-up.sh   (stack deploy)
2:30  demo-logs.sh + demo-run.sh
3:30  MONEY SHOT: parallel SPAWN events
5:00  Final report
6:00  Add-an-agent (slide or live)
7:00  demo-down.sh
7:30  Wrap
```
