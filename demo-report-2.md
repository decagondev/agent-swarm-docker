# Demo Run Report #2

Second end-to-end pass on 2026-05-13, run after the `demo-down.sh` fix. Same host, same provider as run #1 (Groq, `llama-3.3-70b-versatile`). Goal of this pass: confirm the teardown fix on a real run and capture a clean baseline with no outstanding bugs.

## TL;DR

Everything is green. Warm-cache `demo-up.sh` is now ~2 s. A fresh prompt drove a different mix of agents (3 in parallel again, but the LLM chose `capitalize` instead of `count_consonants` this time — substitutability of agents at the planning layer also works). `demo-down.sh` now cleanly removes the shared-data volume, no silent leak. No regressions surfaced.

| Step | Time | Status |
|---|---|---|
| `demo-up.sh` (warm cache) | 1.9 s | ✅ |
| Supervisor 1/1 replica | 1 s | ✅ |
| `demo-run.sh` end-to-end | 5.7 s | ✅ |
| Ephemeral cleanup mid-run | (live) | ✅ |
| `demo-down.sh` (fixed) | 16.9 s | ✅ |
| Volume actually removed | — | ✅ |

---

## 1. `demo-up.sh` — warm path

```bash
bash ./scripts/demo-up.sh
```

```
→ swarm already active
→ image agent-swarm:latest already built (delete it to force rebuild)
→ docker stack deploy -c docker/docker-stack.yml agent-swarm
…
✅ Stack 'agent-swarm' is up.

real    0m1.934s
```

Both short-circuits fired: swarm already initialized, image already built locally. Compared to the ~80 s cold run from report #1, this is essentially the time it takes Docker Desktop to deploy the stack. The supervisor task reported 1/1 replica within 1 s.

This is the path the talk will actually exercise on stage, assuming `demo-up.sh` is run once before the audience arrives to prime the cache.

---

## 2. `demo-run.sh` — fresh prompt, different agent mix

```bash
bash ./scripts/demo-run.sh \
  "Take this product blurb and prepare a launch summary: 'Atlas is a self-hosted feature flag service that ships SDKs for six languages and exposes an audit log of every flip.'"
```

### Supervisor event log

```
→ exec into a3948a31af89 (service agent-swarm_supervisor)
[13:22:44] LLM    iter 0   tools=3
[13:22:44] SPAWN  capitalize         service=nsmvvqsyfqe9  job=job-18154be3
[13:22:44] SPAWN  slogan_generator   service=avoaeapwpypn  job=job-18154be3
[13:22:44] SPAWN  feature_extractor  service=o726i9k1j2yl  job=job-18154be3
[13:22:45] DONE   capitalize          elapsed=1.22s
[13:22:45] CLEAN  capitalize
[13:22:47] DONE   feature_extractor   elapsed=2.62s
[13:22:47] DONE   slogan_generator    elapsed=2.62s
[13:22:47] CLEAN  feature_extractor
[13:22:47] CLEAN  slogan_generator
[13:22:48] LLM    iter 1: final answer   chars=971
```

Total wall: 5.7 s. Most of that is the second LLM round-trip (Groq is fast but still a network hop), not Docker.

### Final answer (stdout)

> The launch summary for the product Atlas is as follows:
> The product Atlas is a self-hosted feature flag service that ships SDKs for six languages and exposes an audit log of every flip.
> As stated by the capitalization agent, the key phrase is: 'ATLAS IS A SELF-HOSTED FEATURE FLAG SERVICE THAT SHIPS SDKS FOR SIX LANGUAGES AND EXPOSES AN AUDIT LOG OF EVERY FLIP.'
> The feature extraction agent found the following key features:
> * Service: flexibility
> * SDKs: multi-language support
> * Audit log: transparency
> * Hosting: control
> * Feature flags: risk management
> * Log: accountability
> The slogan generator agent created the following slogans:
> Take Control of Your Code with Atlas
> Ship Smarter, Not Harder, with Atlas Feature Flags
> Flip the Switch to Seamless Deployment with Atlas
> These points highlight the key aspects of Atlas, including its self-hosted feature flag service, multi-language support, and transparent audit log, making it a valuable tool for developers.

### Live ephemeral service transitions (1 s poller)

```
[14:22:45] ephemeral services: agent-swarm-capitalize-job-18154be3-46d76d        0/1
                              | agent-swarm-feature_extractor-job-18154be3-b5b916 0/1
                              | agent-swarm-slogan_generator-job-18154be3-61a277  0/1
[14:22:46] ephemeral services: agent-swarm-feature_extractor-…-b5b916            1/1
                              | agent-swarm-slogan_generator-…-61a277             1/1
[14:22:47] ephemeral services: (none)
```

Same pattern as run #1: all three services appear simultaneously at 0/1, the fastest one (`capitalize`, 1.2 s) is gone before the next poll tick, and the remaining two reach 1/1 just before they too finish and are reaped. Within ~3 s of spawn, all three are cleaned.

### Shared-volume artifacts (read from inside the supervisor)

| Path | Content |
|---|---|
| `/app/data/input/job-18154be3.txt` | Original prompt |
| `/app/data/results/job-18154be3__capitalize.result` | Prompt text uppercased |
| `/app/data/results/job-18154be3__feature_extractor.result` | 6 noun:benefit bullets |
| `/app/data/results/job-18154be3__slogan_generator.result` | 3 slogans, one per line |

### What changed vs run #1

| | Run 1 | Run 2 |
|---|---|---|
| LLM-picked tools | `count_consonants`, `feature_extractor`, `slogan_generator` | `capitalize`, `feature_extractor`, `slogan_generator` |
| Total wall | ~4 s | ~5.7 s |
| LLM-aware agents in mix | 2 (`feature_extractor`, `slogan_generator`) | 2 (same) |
| Pure-CPU agent | `count_consonants` | `capitalize` |
| Final answer length | 633 chars | 971 chars |

Both runs exercised the same pattern (1 pure-CPU agent + 2 LLM-aware agents in parallel). The fact that the supervisor LLM swapped one for the other on a different prompt is a nice incidental demonstration of the Open/Closed design — adding/removing tools doesn't require any change to the supervisor.

**Right**: all of the above. Result aggregation, dual-mode agents (LLM-aware vs not), service cleanup, file-handoff via shared volume, second-turn final answer — all behaving identically to run #1 with different inputs.

**Wrong**: nothing.

---

## 3. `demo-down.sh` — fixed teardown

```bash
bash ./scripts/demo-down.sh
```

```
→ docker stack rm agent-swarm
→ waiting for services and task containers to fully tear down
→ removing volume agent-swarm_shared-data (if present)
agent-swarm_shared-data
✅ Teardown complete.

real    0m16.926s
```

The wait loop now blocks for ~16 s — the extra ~10 s vs. the buggy version is the supervisor task container actually exiting after `docker stack rm`. The single line `agent-swarm_shared-data` between the third arrow and the green checkmark is `docker volume rm` echoing back the volume it removed; that's the proof the rm succeeded.

### Post-teardown verification

```text
Services (label=agent-swarm.role):        (empty)
Containers (stack namespace):             (empty)
Volumes (agent-swarm prefix):             (empty)
```

All three are zero. The bug from report #1 is fixed.

### What changed in `scripts/demo-down.sh`

Wait loop now polls *both* service count and task-container count, since on Docker Desktop the container can outlive its service for several seconds:

```bash
for _ in {1..30}; do
  svcs="$(docker service ls --filter "label=com.docker.stack.namespace=${STACK}" -q | wc -l)"
  ctrs="$(docker ps -aq --filter "label=com.docker.stack.namespace=${STACK}" | wc -l)"
  if [[ "$svcs" -eq 0 && "$ctrs" -eq 0 ]]; then break; fi
  sleep 1
done
```

Volume removal now surfaces its own error instead of swallowing it:

```bash
if docker volume inspect "${STACK}_shared-data" >/dev/null 2>&1; then
  if ! docker volume rm "${STACK}_shared-data"; then
    echo "⚠️  volume ${STACK}_shared-data still in use; leaving in place" >&2
  fi
fi
```

The `inspect` guard preserves the "absent volume is fine" behavior — on a fresh cluster where teardown is called before deploy, this still no-ops without complaint.

### Trade-off

The fix slows teardown from ~6 s to ~17 s. Acceptable for a demo (you tear down after the talk, not during it), and the alternative — silently leaking volumes — is worse. If teardown speed ever matters, the right move is `docker container rm -f` the lingering task container after the service wait, not extending the polling deadline.

---

## 4. Outstanding items (unchanged from report #1)

The fix only touched the volume-leak issue. The other findings from report #1 are still open:

- **CRLF line endings** on `scripts/*.sh`. Git Bash tolerates it; WSL bash and Linux containers' bash will not. A `.gitattributes` with `*.sh text eol=lf` is a one-line fix that would also be tracked by every future contributor's `git checkout`.
- **Clock skew** between supervisor container (UTC) and host (local TZ). Cosmetic but confusing when correlating monitor output with supervisor logs. No fix proposed — it's just how containers vs. host time work, and the supervisor's UTC-ish timestamps are fine to leave.
- **Long Swarm-generated service names** (`agent-swarm-capitalize-job-18154be3-46d76d`). Wrap awkwardly in narrow terminals on stage. Not worth fixing for the talk; useful to know if it bites you visually during rehearsal.

---

## Verdict

Demo path is in good shape for the talk:

1. **Pre-talk**: run `./scripts/demo-up.sh` once to prime the image cache. Future runs take ~2 s.
2. **On stage**: `./scripts/demo-run.sh "…"` returns a final answer in ~4–6 s with 2–3 services visibly spawning and reaping in parallel.
3. **After the talk**: `./scripts/demo-down.sh` actually cleans up, including the volume.

No bugs currently outstanding in the live demo flow itself.
