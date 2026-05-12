# Live Demo Run Report — `agent-swarm-docker`

**Run timestamp:** 2026-05-12T11:35:06Z (UTC)
**Prompt:** `The quick brown fox jumps over the lazy dog while coding with Docker Swarm.`
**Executor:** `swarm` (full Docker Swarm path)
**LLM provider:** Groq · model `llama-3.3-70b-versatile`
**Final exit code:** `0` (success on retry attempt 1)

---

## 1. Environment

| Item | Value |
|---|---|
| Docker Engine | `29.4.3` |
| Swarm state | `active` |
| Host Python | `3.12.3` |
| Supervisor image | `agent-swarm:latest` |
| Image digest | `sha256:26766d5cad64e71e60e954cd2592679aca92821e789553d3f1e42c025f36fac6` |

---

## 2. Phase 1 — `./scripts/demo-up.sh`

`docker swarm init` was already active (idempotent). Image build was skipped (cached locally). Stack deploy created the `agent-swarm_supervisor` service.

```
→ swarm already active
→ image agent-swarm:latest already built (delete it to force rebuild)
→ docker stack deploy -c docker/docker-stack.yml agent-swarm
Creating network agent-swarm_agent-swarm-net
Creating service agent-swarm_supervisor

✅ Stack 'agent-swarm' is up.
```

Pre-run service list (only the long-lived supervisor):

```
ID             NAME                     MODE         REPLICAS   IMAGE
1nlmu3xs6oa7   agent-swarm_supervisor   replicated   1/1        agent-swarm:latest
```

---

## 3. First invocation — failed with `tool_use_failed`

The first run of `./scripts/demo-run.sh` failed at the very first LLM round. Llama 3.3 70b on Groq emitted a malformed tool call envelope that Groq's strict tool-use validator rejected:

```
openai.BadRequestError: Error code: 400 - {'error': {
  'message': "Failed to call a function. Please adjust your prompt. ...",
  'type': 'invalid_request_error',
  'code': 'tool_use_failed',
  'failed_generation': '<function=capitalize [{"input_ref": "job-30837154"}](input_ref)</function>\n'
}}
```

**Time-to-failure:** 2.05s. No agent services were spawned because the supervisor crashed before issuing tool calls.

**Why this happens:** Llama models on Groq occasionally emit tool calls in a non-canonical text format instead of the expected JSON structure. Groq's API validates the format strictly and rejects malformed output. This is a stochastic Llama behaviour, not a code bug — the same prompt succeeded on the immediately following retry.

**Mitigation for production:** wrap `LLMClient.chat` with retry-on-`tool_use_failed` (1–2 retries usually suffice). Not implemented in this codebase — flagged as a follow-up.

---

## 4. Retry — successful run

```
Wall time: 6.14s · exit 0
```

### 4.1 Supervisor event log (stderr)

```
→ exec into 45734035f8f3 (service agent-swarm_supervisor)
[11:36:46] LLM    iter 0   tools=7
[11:36:46] SPAWN  capitalize         service=l6xnfnbj4i3d  job=job-7261f802
[11:36:46] SPAWN  reverse            service=c9o0enfcno8i  job=job-7261f802
[11:36:46] SPAWN  count_consonants   service=zrbvu18ri0j7  job=job-7261f802
[11:36:46] SPAWN  feature_extractor  service=qa3vn5dua6y8  job=job-7261f802
[11:36:46] SPAWN  vowel_random       service=axg0icbdxsiw  job=job-7261f802
[11:36:46] SPAWN  slogan_generator   service=wp546y22dr2v  job=job-7261f802
[11:36:46] SPAWN  translator         service=tcah0rbcrqtr  job=job-7261f802
[11:36:48] DONE   capitalize         job=job-7261f802  elapsed=1.61s
[11:36:48] CLEAN  capitalize         service=l6xnfnbj4i3d
[11:36:48] DONE   reverse            job=job-7261f802  elapsed=1.62s
[11:36:48] DONE   count_consonants   job=job-7261f802  elapsed=1.62s
[11:36:48] DONE   vowel_random       job=job-7261f802  elapsed=1.62s
[11:36:48] CLEAN  reverse            service=c9o0enfcno8i
[11:36:48] CLEAN  count_consonants   service=zrbvu18ri0j7
[11:36:48] CLEAN  vowel_random       service=axg0icbdxsiw
[11:36:49] DONE   feature_extractor  job=job-7261f802  elapsed=2.82s
[11:36:49] DONE   translator         job=job-7261f802  elapsed=2.82s
[11:36:49] CLEAN  feature_extractor  service=qa3vn5dua6y8
[11:36:49] CLEAN  translator         service=tcah0rbcrqtr
[11:36:49] DONE   slogan_generator   job=job-7261f802  elapsed=3.02s
[11:36:49] CLEAN  slogan_generator   service=wp546y22dr2v
[11:36:50] LLM    iter 1: final answer   chars=897
```

The supervisor LLM emitted all **7 tool calls in a single turn** (iter 0 → 7 parallel spawns), the agents ran concurrently as ephemeral Swarm services, and a single follow-up LLM call (iter 1) produced the final synthesis. Total of 2 LLM round-trips end-to-end.

### 4.2 `docker service ls` snapshots during fan-out

Captured every second from a parallel monitor. Each row is the agent's service name + replica state.

**T+01s** — supervisor still resolving its tool calls; no agents yet:
```
(no ephemeral services)
```

**T+02s** — all 7 services created, tasks not yet running:
```
agent-swarm-capitalize-job-7261f802-6c408b         rep=0/1
agent-swarm-count_consonants-job-7261f802-7750cf   rep=0/1
agent-swarm-feature_extractor-job-7261f802-fb96bd  rep=0/1
agent-swarm-reverse-job-7261f802-81b51b            rep=0/1
agent-swarm-slogan_generator-job-7261f802-6c7c38   rep=0/1
agent-swarm-translator-job-7261f802-94fa9c         rep=0/1
agent-swarm-vowel_random-job-7261f802-6cd708       rep=0/1
```

**T+03s** — 6 of 7 tasks now running (`1/1`). `count_consonants` is the last to start:
```
agent-swarm-capitalize-job-7261f802-6c408b         rep=1/1
agent-swarm-count_consonants-job-7261f802-7750cf   rep=0/1
agent-swarm-feature_extractor-job-7261f802-fb96bd  rep=1/1
agent-swarm-reverse-job-7261f802-81b51b            rep=1/1
agent-swarm-slogan_generator-job-7261f802-6c7c38   rep=1/1
agent-swarm-translator-job-7261f802-94fa9c         rep=1/1
agent-swarm-vowel_random-job-7261f802-6cd708       rep=1/1
```

**T+04s** — the four simple agents have already exited and been cleaned up. Only the three LLM-aware agents remain:
```
agent-swarm-feature_extractor-job-7261f802-fb96bd  rep=1/1
agent-swarm-slogan_generator-job-7261f802-6c7c38   rep=1/1
agent-swarm-translator-job-7261f802-94fa9c         rep=1/1
```

**T+05s, T+06s** — all services gone, supervisor exited successfully.

---

## 5. Per-agent results

The shared volume contained these files after the run (sizes in bytes):

```
job-7261f802__capitalize.result          75
job-7261f802__count_consonants.result     2
job-7261f802__feature_extractor.result  166
job-7261f802__reverse.result             75
job-7261f802__slogan_generator.result   112
job-7261f802__translator.result         101
job-7261f802__vowel_random.result        38
```

### 5.1 `capitalize`
```
THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG WHILE CODING WITH DOCKER SWARM.
```
Byte-perfect uppercase of the input. ✓

### 5.2 `reverse`
```
.mrawS rekcoD htiw gnidoc elihw god yzal eht revo spmuj xof nworb kciuq ehT
```
Byte-perfect character-by-character reverse. ✓

### 5.3 `count_consonants`
```
42
```
42 consonants in the input (matches the reference algorithm: `sum(1 for c in text if c.isalpha() and c not in {a,e,i,o,u,A,E,I,O,U})`). ✓

### 5.4 `vowel_random`
```
SHKWy10V69bup2Y4anu1bydtLjXZHdia8CK06t
```
38 alphanumeric characters = 19 vowels × 2. Length and alphabet correct. ✓

### 5.5 `feature_extractor` (LLM-aware)
```
* Docker Swarm + efficient coding
* Coding + productivity
* Docker + containerization
* Swarm + clustering
* Containerization + flexibility
* Clustering + scalability
```
6 noun + benefit pairs, on-task, no extraneous content. ✓

### 5.6 `slogan_generator` (LLM-aware)
```
Code Smarter, Not Harder with Docker Swarm
Unlock Efficiency, Unleash Innovation
Containerize Your Future, Today
```
3 catchy slogans, no extra content. ✓

### 5.7 `translator` (LLM-aware)
```
Le rapide renard brun saute par-dessus le chien paresseux pendant la programmation avec Docker Swarm.
```
Idiomatic French translation. ✓

---

## 6. Final synthesised report (Supervisor LLM, iter 1, 897 chars)

```
The user task is to analyze the given text "The quick brown fox jumps over the
lazy dog while coding with Docker Swarm."

The capitalized text is "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG WHILE
CODING WITH DOCKER SWARM."
The reversed text is ".mrawS rekcoD htiw gnidoc elihw god yzal eht revo spmuj
xof nworb kciuq ehT".
The key features are "* Docker Swarm + efficient coding * Coding + productivity
* Docker + containerization * Swarm + clustering * Containerization +
flexibility * Clustering + scalability".
The vowel-based random string is "SHKWy10V69bup2Y4anu1bydtLjXZHdia8CK06t".
The consonant count is "42".
The marketing slogans are "Code Smarter, Not Harder with Docker Swarm Unlock
Efficiency, Unleash Innovation Containerize Your Future, Today".
The French translation is "Le rapide renard brun saute par-dessus le chien
paresseux pendant la programmation avec Docker Swarm."
```

Llama quoted **every agent output verbatim** in this run — the same model paraphrased on previous runs. This is model-quality variance, not a system problem.

---

## 7. Timing breakdown

| Agent | Type | Elapsed (s) | Notes |
|---|---|---:|---|
| capitalize | simple | 1.61 | container startup–dominated |
| reverse | simple | 1.62 | container startup–dominated |
| count_consonants | simple | 1.62 | container startup–dominated |
| vowel_random | simple | 1.62 | container startup–dominated |
| feature_extractor | LLM-aware | 2.82 | +1.2s for Groq round-trip |
| translator | LLM-aware | 2.82 | +1.2s for Groq round-trip |
| slogan_generator | LLM-aware | 3.02 | +1.4s for Groq round-trip |

**End-to-end wall time:** 6.14 s
- Supervisor's LLM iter 0 (planning): ~1.0 s
- Parallel agent fan-out: ~3.0 s (bounded by slowest LLM-aware agent)
- Supervisor's LLM iter 1 (synthesis): ~1.0 s
- Overhead (CLI exec, container start): ~1.1 s

The 7 agents ran **truly in parallel** — total wall time (3.02 s for fan-out) is bounded by the *slowest* agent, not the sum (which would be ~14 s serial).

---

## 8. Teardown

```
→ docker stack rm agent-swarm
→ waiting for services to fully tear down
→ removing volume agent-swarm_shared-data (if present)
✅ Teardown complete.
```

Post-teardown `docker service ls` is empty. Swarm node remains active (no `--leave-swarm` flag passed).

---

## 9. Observations / lessons from this run

1. **Tool-use validation is provider-specific.** Groq rejects malformed tool calls with `tool_use_failed` (400). OpenAI tends to silently retry the generation. This is an argument for adding a thin retry layer in `LLMClient`.
2. **Llama is stochastic on tool-call formatting.** Of the two runs in this session, attempt 1 failed with malformed tool calls, attempt 2 succeeded. The fix is at the LLMClient layer (retry), not the supervisor.
3. **Parallel fan-out is real.** Snapshot at T+03s shows 6 of 7 Swarm services in `1/1` state simultaneously — visible proof of the architectural claim.
4. **The shared volume is the wire.** Every agent output is a file on the named `agent-swarm_shared-data` volume. The supervisor reads them back via `ResultWatcher`. No message queue needed.
5. **Container startup is the floor.** Even the trivial agents (capitalize, reverse) take ~1.6 s because of Swarm task scheduling + container start. Beating this would require a long-lived agent pool — at which point you've reinvented a worker queue.
6. **The retry attempt re-used the cached image** — no rebuild, no `docker swarm init`. Demo-up was idempotent, which is what we want on stage.
