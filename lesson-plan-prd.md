# Lesson Plan PRD: Docker Swarm Agent Swarm Demo  

## 1. Project Goal / Lesson Objective

**Big Idea for the Talk (5–10 min live demo):**  
Show how Docker Swarm turns a simple “orchestrator + workers” pattern into a **production-grade, parallel AI agent swarm** where a **Supervisor LLM** treats specialized agents as **tools**.  

The supervisor LLM receives a high-level task → breaks it into subtasks → calls tools that **dynamically spin up sub-agent services in the Swarm** → agents run **in true parallel** → results are aggregated.  

**Key Teaching Moments (show code + live running):**  
- Docker Swarm (single-node for demo) enables effortless scaling, service discovery, and parallel execution.  
- SOLID + modular Python design makes the system extensible (add new agent types in <10 lines).  
- AI-first devs see how Docker is the “runtime for agent swarms” – no Kubernetes complexity.  

**Target Audience:** AI-first developers who already know LLMs / LangChain but are new to Docker/Swarm.  

**Demo Outcome:** Audience walks away with a working repo they can `git clone` and run in 2 minutes, plus clear mental model of “LLM → Docker Swarm → Parallel Agents”.

## 2. Demo Scenario (Live Talk Flow – 8 minutes)

**Prompt given to Supervisor LLM (live in talk):**  

Analyze this product description for our new "Docker Agent" tool:  
"The quick brown fox jumps over the lazy dog while coding with Docker Swarm."

Break it down and do the following **in parallel**:
1. Extract key features (nouns + benefits).
2. Generate 3 catchy marketing slogans.
3. Translate ONE slogan to French.
4. Count consonants & generate a "random vowel-inspired" string (fun Easter egg).
5. Reverse the original description for a "backwards compatibility" joke.
Return a polished final report.


**What the audience sees live:**
1. `docker swarm init` (single-node).
2. `docker stack deploy -c docker-stack.yml agent-swarm` (shows Swarm services).
3. Run new `supervisor.py "..."` → LLM decides subtasks.
4. Terminal splits / `docker service ls` + `docker service logs` show **4–5 sub-agent services spinning up in parallel** (each a short-lived Swarm task).
5. Shared volume + results appear instantly.
6. Final report prints with citations to each agent’s output.
7. Tear-down: `docker stack rm agent-swarm` (clean demo).

**Why this scenario is perfect:**
- Simple text processing (builds directly on current `worker.py` tasks).
- Clearly demonstrates **parallelism** (visible in logs).
- Supervisor LLM uses **agents as tools** (function calling).
- 100% Docker-native – no external queues or databases needed for the demo.

## 3. High-Level Architecture (Post-Extension – Modular & SOLID)

**Core Principles Applied:**
- **S**ingle Responsibility: Each module does one thing.
- **O**pen/Closed: Add new agent type → no change to supervisor or swarm manager.
- **L**iskov Substitution: All agents interchangeable via abstract `Agent` interface.
- **I**nterface Segregation: Tiny `Tool` and `SwarmTask` interfaces.
- **D**ependency Inversion: Supervisor depends on `AgentRegistry` abstraction, not concrete workers.

**New Folder Structure (modular):**
```
agent-swarm-docker/
├── core/
│   ├── supervisor.py          # LLM + tool calling
│   ├── agent_registry.py      # Open/Closed registry of agents
│   └── swarm_manager.py       # Docker SDK + Swarm service lifecycle
├── agents/
│   ├── base.py                # Abstract Agent + Tool interface
│   ├── capitalize.py
│   ├── reverse.py
│   ├── feature_extractor.py   # New LLM-aware agents
│   └── slogan_generator.py
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml     # Backward compat (local dev)
│   └── docker-stack.yml       # Swarm deploy (new)
├── shared-data/               # .gitignored volume mount
├── supervisor.py              # CLI entrypoint
├── worker.py                  # Legacy single-task (kept for compatibility)
└── lesson-plan-prd.md         # ← this file
```

**Communication:** Keep shared volume (simple, zero-deps) + optional Redis later (open for extension).

## 4. Epics & User Stories

### Epic 1: Modular Refactoring (SOLID Foundation)
**Goal:** Turn monolithic scripts into extensible library.

- **US1.1** – Extract abstract `BaseAgent` and `Tool` interfaces (Liskov + Interface Segregation).  
- **US1.2** – Create `AgentRegistry` (Open/Closed) with decorator `@register_agent`.  
- **US1.3** – Refactor `worker.py` tasks into concrete agent classes.  
- **US1.4** – Dependency-invert orchestrator to use registry.

### Epic 2: Supervisor LLM Integration
**Goal:** Replace hardcoded logic with LLM that uses agents as tools.

- **US2.1** – Add `supervisor.py` using xAI/Groq/OpenAI function calling (configurable via env).  
- **US2.2** – Define 5 example tools that map to agent names (e.g. `spawn_feature_extractor`).  
- **US2.3** – LLM prompt engineering template for task decomposition + tool selection.  
- **US2.4** – Aggregation logic: collect results → final LLM summary.

### Epic 3: Dynamic Sub-Agent Spawning with Docker Swarm
**Goal:** Supervisor triggers real parallel Docker Swarm services.

- **US3.1** – Implement `SwarmManager` using `docker` Python SDK (create/update/scale/rm services).  
- **US3.2** – Add `docker-stack.yml` with Swarm deploy configs + labels.  
- **US3.3** – Each tool call → `swarm_manager.spawn_agent(task_type, input_id)` (temporary service with `replicas=1`, auto-cleanup).  
- **US3.4** – Polling / event-driven result collection (shared volume + file watcher for demo speed).

### Epic 4: Agent Tools & Parallel Execution Demo
**Goal:** Polish the live demo experience.

- **US4.1** – Extend registry with LLM-friendly tool schemas (JSON schema for function calling).  
- **US4.2** – Add visual logging (`rich` or colored output) showing “Spawning X-agent (service abc123)”.  
- **US4.3** – Demo helper scripts: `demo-start.sh`, `demo-logs.sh`, `demo-teardown.sh`.

### Epic 5: Lesson Materials & Talk Assets
**Goal:** Make the talk plug-and-play.

- **US5.1** – Add `README-DEMO.md` with exact talk script + commands.  
- **US5.2** – Include 3 slide screenshots (architecture, Swarm services, live logs).  
- **US5.3** – CI check: `make test-demo` that runs full swarm flow in CI (single-node).

## 5. Commit Slices (Atomic, Reviewable, Teachable)

Each commit is <200 LOC, has clear title, and can be shown live in the talk.

**Epic 1 (Refactoring – 6 commits)**
1. `refactor: add core/ package + abstract BaseAgent (SOLID S/L)`
2. `refactor: implement AgentRegistry with @register_agent decorator (O)`
3. `refactor: migrate all worker tasks to concrete agents`
4. `refactor: dependency-invert legacy orchestrator`
5. `chore: update docker-compose.yml for new structure`
6. `test: add pytest for registry`

**Epic 2 (LLM Supervisor – 5 commits)**
7. `feat: add supervisor.py with LLM function calling`
8. `feat: define tool schemas for all registered agents`
9. `feat: prompt template + task decomposition`
10. `feat: result aggregation + final LLM summary`

**Epic 3 (Swarm Spawning – 5 commits)**
11. `feat: add SwarmManager using docker SDK`
12. `feat: docker-stack.yml + Swarm labels`
13. `feat: tool → swarm_service.spawn_agent(...)`
14. `feat: auto-cleanup of temporary services`
15. `docs: add Swarm init instructions`

**Epic 4 & 5 (Polish & Demo)**
16–20. Small feature + docs commits (visual logs, helper scripts, README-DEMO.md, etc.)

**Branch Strategy:**  
`feature/modular-refactor` → `feature/llm-supervisor` → `feature/swarm-dynamic` → `main`  
Each PR = 1 Epic (easy review + talk demo).

## 6. Non-Functional Requirements

- **Backward Compatible:** `docker compose up` still works exactly as today.
- **Zero new heavy deps** for core demo (only `docker` SDK + `requests`/`openai` optional).
- **Fast iteration:** Full swarm cycle < 30 seconds.
- **Secure defaults:** No root, read-only volumes where possible.
- **Extensible:** New agent = add Python file + `@register_agent` decorator.

## 7. Acceptance Criteria / Demo Checklist

- [ ] Live demo runs end-to-end in <8 minutes on stage laptop.
- [ ] All new code follows SOLID (verified by simple architecture diagram).
- [ ] Supervisor LLM successfully spawns 4+ parallel sub-agents visible in `docker service ls`.
- [ ] Final report contains clear attribution (“Result from feature-extractor-agent-xyz”).
- [ ] Repo README + README-DEMO.md makes it 2-command install for audience.
- [ ] Talk script + code diffs ready to copy-paste into slides.

Ready to ship the first epic? Let’s make this the best Docker + AI agents talk ever! 🚀
