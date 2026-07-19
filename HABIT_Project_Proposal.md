# HABIT — Harnessing Agent Behavior Into deterministic Tasks

**Tagline:** *Muscle memory for AI agents. Decide once, execute forever.*

**Project type:** Major Project (two semesters) · Team of 5 · AI Systems / Agentic AI
**Target outcomes:** Working open-source library + live demo + benchmark + research paper submission

---

## 1. Problem Statement

### 1.1 The problem in one story

Imagine a new employee on their first day at work. Every task is new, so they think hard, ask questions, and work slowly. That thinking is expensive. But after doing the same task fifty times, they stop thinking about it — they just do it, fast and almost effortlessly, on muscle memory. Their brain switches back on only when something unusual happens.

Today's AI agents are stuck on "day one" forever. An agent built with frameworks like LangGraph or CrewAI treats its 10,000th invoice exactly like its 1st — it calls a large language model (LLM) at every single step, pays the full cost of "fresh thinking" every time, and takes the full time, even though the task is identical to thousands it has already completed successfully.

### 1.2 The three concrete pains this causes

**Pain 1 — Cost.** Every step of an agent run is an LLM call. A single run of a moderately complex agent workflow can cost anywhere from a fraction of a rupee to ₹30+ depending on the model. Companies want to run these workflows lakhs or millions of times a month (ticket triage, invoice processing, report generation, claims handling). At that scale, per-run inference cost is the number one blocker stopping companies from actually deploying agents widely. Industry studies report up to 50x cost variation between systems achieving similar accuracy — meaning most deployments are massively overpaying for repeated work.

**Pain 2 — Reliability.** LLMs are probabilistic: even a very good agent might be ~85% reliable at each individual step. Simple math shows the disaster this creates on long tasks — a 10-step workflow at 85% per-step reliability succeeds end-to-end only about 20% of the time. The agent isn't "wrong"; the *system* has no way to make repeated, well-understood steps deterministic and safe. Enterprises consistently report a large gap (~37%) between how agents score on lab benchmarks and how they perform in real deployments.

**Pain 3 — Context overflow (agent amnesia).** An agent's "working memory" is its context window — like a small desk. Current agents pile every document, every tool result, and the entire conversation onto that desk until it overflows. Then things get cut off arbitrarily — sometimes the important things — and on long-horizon tasks the agent literally forgets its own goal halfway through. Today, "context engineering" is done by hand with ad-hoc rules; there is no principled, automatic system for deciding what an agent should keep in memory at each step.

### 1.3 Why these are really ONE problem

All three pains share a single root cause: **agents re-derive, at runtime, knowledge they already possess in their own history.** The agent has already proven — hundreds of times — which steps a task needs, in what order, and which information each step actually uses. Nothing in today's agent stack learns from that history. Our project fixes all three pains with one mechanism: learning the agent's habits from its own past runs.

---

## 2. Proposed Solution

### 2.1 The idea in simple words

HABIT is a **self-optimizing runtime layer** that wraps around an existing agent (built in LangGraph or similar). It does four things:

1. **Watches** the agent work and records every run like a diary.
2. **Notices** which tasks the agent performs repeatedly in the same way.
3. **Freezes** the repetitive parts into ordinary, deterministic computer code (a "habit") — which is essentially free to run and never has an off day — keeping tiny, cheap LLM calls only for the steps that genuinely need judgment.
4. **Stays alert:** when a new task doesn't fit any learned habit, or a run starts going off-script mid-way, HABIT detects it and instantly hands control back to the full "thinking" agent. That new experience then goes back into the diary — so the system gets cheaper, faster, and smarter the longer it runs.

An intuitive framing (useful in presentations): this is **System 1 / System 2 thinking for AI agents.** Habits are System 1 — fast, cheap, automatic. The live LLM agent is System 2 — slow, expensive, deliberate. HABIT decides, at every moment, which system should be driving.

A second framing for technical audiences: HABIT is a **JIT (just-in-time) compiler plus virtual memory, but for AI agents.** "Hot paths" (frequently repeated workflows) get compiled to cheap deterministic code; "cold paths" (novel tasks) stay interpreted by the live LLM; and context is paged in and out of the window the way an operating system pages memory.

### 2.2 The four layers of the system (detailed but simple)

**Layer 1 — The Flight Recorder (Observation).**
A lightweight wrapper around the agent framework that logs every run as a structured "trajectory": the task, every step taken, every tool called (with inputs and outputs), what information was in the context at each step, and the final outcome (success/failure). Think of it as a black-box flight recorder for agents. This layer must be boring, reliable, and invisible — everything else is built on top of it.

**Layer 2 — The Habit Compiler (Workflow Crystallization).**
Runs offline, periodically. It groups similar past trajectories together (clustering), aligns them to find the **stable skeleton** — the sequence of steps that appears in essentially every successful run of that task type — and identifies which steps are always identical vs. which ones genuinely vary. It then generates real, executable Python code for the stable skeleton. Variable steps remain as small LLM calls, routed to a tiny cheap local model instead of the big expensive one. Crucially, before any compiled habit is allowed to serve real traffic, it is **replay-validated**: we re-run it against dozens of recorded past trajectories and check it produces the correct outcomes. Unvalidated habits never go live.

**Layer 3 — The Context Compiler (Learned Memory Policies).**
Here is the elegant part of our design: once we have hundreds of recorded trajectories, we know *exactly which pieces of information each step actually used*. If the "validate invoice" step never once read the email thread, it doesn't need the email thread on its desk. Layer 3 turns these observed access patterns into **per-step context policies**: what stays in the context window, what gets filed away into an external store, and what gets fetched back just before the step that needs it (prefetching). This replaces hand-written context-engineering rules with policies **learned automatically from usage** — and it directly prevents the "agent amnesia" failure on long tasks.

**Layer 4 — The Runtime with a Safety Net (Routing, Divergence Detection, Fallback).**
This is the live, always-on component and the research heart of the project. When a new task arrives, the router checks: does this match a known habit? If yes → run the cheap compiled path. If no → run the full live agent (and record it, feeding Layer 1). While a habit is running, a **divergence detector** watches every step: does the tool output match the schemas we've always seen? Are intermediate results within the normal range? The moment something looks off-script, HABIT pauses the habit, pages the relevant context back in, and **re-inflates** to the full live agent, which handles the situation. If the world has genuinely changed (e.g., an API changed its format), the habit is marked stale and recompiled from fresh trajectories — the "recompile-on-drift" loop.

### 2.3 What is genuinely new (the research contributions)

We are not the first to notice that agent runs contain reusable structure — and that's good news, because it proves the direction is publishable. Prior work includes: Agent Workflow Memory (AWM, 2024 — induces workflows but stores them as *natural-language text*, re-interpreted by the LLM each time), Trace2Skill (2026 — structured skill documents, still text), Skill-DisCo (2026 — compiles skills into executable code, but as an **offline, one-shot study**), AFlow / ADAS (optimize workflow graphs, but every node remains an LLM call), and Anthropic's Claude Code "dynamic workflows" (closed-source, Claude-only). Our gaps — the things nobody has built:

1. **The closed online loop as a runtime.** Observe → compile → route live traffic → detect mid-run divergence → fall back gracefully → recompile on drift. Divergence detection with safe fallback is an open research problem and our core contribution. A compiler without this safety net is just a cron job.
2. **Connecting compilation to context management.** No existing work induces *context policies* from trajectories. This link — the compiler telling the memory system what each step needs — appears in no prior paper and is our clearest novelty claim.
3. **A public cost–reliability benchmark.** A reusable benchmark measuring the trade-off frontier of (cost, latency, success rate) as compilation gets more aggressive, across multiple workflow domains, with baselines. The field explicitly lacks standardized agent-reliability evaluation; this artifact will be cited.
4. **Framework-agnostic and open-source**, unlike the closed industrial versions.

### 2.4 Research questions we will answer

- **RQ1:** How much cost and latency can trajectory-compiled workflows save versus a live agent, at equal or better success rates? (Target: demonstrate 10–100x cost reduction on repeat runs across 3 domains.)
- **RQ2:** Can mid-run divergence be detected reliably? What is the trade-off between missed divergences (silent failures) and false aborts (unnecessary fallbacks to the expensive agent)?
- **RQ3:** Do learned per-step context policies reduce token usage and improve long-horizon task survival versus naive full-context execution?
- **RQ4:** How does the (cost, latency, accuracy) Pareto frontier shift as compilation aggressiveness increases?

---

## 3. Complete Tech Stack (student perspective — what and why)

| Component | Technology | Why this choice (student view) |
|---|---|---|
| Language | Python 3.11+ | Team already expert; entire agent ecosystem is Python |
| Packaging | pyproject.toml, pip-installable | "Installable library" is itself a deliverable; looks professional |
| Agent framework (wrapped) | LangGraph (first), OpenAI Agents SDK (semester 2) | Team has built two LangGraph systems already; exposes callbacks for easy instrumentation; second adapter proves framework-agnostic claim |
| Big "thinking" LLM | Groq — Llama-3.3-70B | Free tier, very fast, team already uses it — zero budget needed |
| Small "habit" LLM | Ollama — Llama-3.1-8B / Qwen-2.5-7B (local) | Free, runs on a laptop; the price gap between big and small model IS the demo |
| Trajectory schema | Pydantic models (+ align with OpenTelemetry GenAI conventions) | Strict validation catches bugs early; OTel alignment signals production seriousness |
| Storage | SQLite (upgrade path: Postgres) | Zero setup, perfect for a student project; don't gold-plate |
| Embeddings | sentence-transformers (local, e.g., bge-small) | Free, local, team used it in two prior projects |
| Clustering | scikit-learn (HDBSCAN / agglomerative) | Standard, well-documented, easy to tune |
| Sequence alignment | difflib / custom multiple-sequence alignment over tool-call tokens | Simple first, sophisticated later — start with what works |
| Code generation (crystallizer) | Groq LLM writes Python from the skeleton | LLM-assisted codegen, but ALWAYS replay-validated before deployment |
| Replay validation | pytest harness auto-generated per habit | Our safety guarantee and a key differentiator from prior work |
| Prompt optimization (residual calls) | DSPy | Team already knows it from ARIA; optimizes the small model's prompts |
| Divergence detection v1 | Pydantic schema checks + embedding-distance thresholds | Deterministic, explainable, easy to debug |
| Divergence detection v2 | XGBoost classifier over step features | Semester-2 upgrade; team has XGBoost experience |
| Runtime API | FastAPI + Uvicorn | Team's standard backend stack (used in all three prior projects) |
| Context store | SQLite / Redis | Simple key-value "filing cabinet" for paged-out context |
| Token accounting | tiktoken | Precise measurement of context savings |
| Dashboard & demo | React + Recharts over FastAPI websockets | Team's existing frontend stack; live cost meters need websockets. Fallback: Streamlit if time is short |
| Experiment tracking | CSV + notebooks (wandb optional) | Keep it light; reproducibility over tooling |
| Repo & CI | GitHub org, GitHub Actions, pytest, ruff | The repo is a deliverable — treat it like a product |

**Total budget required: ₹0.** Every component is free-tier or local. No GPUs, no proprietary data, no ethics approvals — all workloads are generated by the team itself.

---

## 4. Detailed Approach (phase-by-phase methodology)

### Phase 0 — Foundations (Weeks 1–2)
Everyone reads the four key prior works (AWM, Skill-DisCo, AFlow, and an agent-reliability framework paper) and writes a half-page "what is their gap" note — these notes become the literature review for free. Then the whole team, together, defines on paper: (a) the trajectory schema, and (b) the interfaces between the four layers. This is the single highest-leverage activity of the project: clean interfaces are what allow five people to build in parallel without blocking each other.

### Phase 1 — Instrumentation + Workloads (Weeks 3–6)
Build the flight recorder (Layer 1) and — equally important — the **synthetic workload generators** for three realistic domains: invoice processing, support-ticket triage, and report generation. Each generator produces parameterized tasks with mock tools and automatic ground-truth checkers (so success/failure is measured objectively, not judged by an LLM). This is unglamorous work and it is the most important artifact of semester 1: every experiment downstream depends on it.
**Milestone:** 1,000+ logged trajectories per domain from a vanilla LangGraph agent.

### Phase 2 — First Habit Compiler (Weeks 7–12)
Cluster trajectories → extract stable skeletons → generate executable Python → replay-validate → execute compiled habits on fresh tasks.
**Milestone (end of Semester 1):** the headline results table — *cost per run, latency, and success rate: live agent vs. compiled habit, for each of the three domains, over 1,000+ runs.* A result like "94% of repeat tasks matched a habit, 40x cheaper, success rate up 12 points" wins the semester review outright.

### Phase 3 — The Runtime Loop (Weeks 13–17, Semester 2)
Build the router, divergence detector, fallback/re-inflation mechanism, and recompile-on-drift.
**Milestone:** inject adversarial and novel tasks (malformed inputs, changed tool schemas, out-of-distribution requests) and measure: divergence catch-rate, false-abort rate, and end-to-end success with the safety net active.

### Phase 4 — The Context Compiler (Weeks 16–20, overlapping)
Induce per-step context manifests from trajectory access patterns; implement paging and prefetching; run the long-horizon survival experiment: the same 50-step task with naive full-context handling (which dies of overflow) versus HABIT's paged context (which finishes).
**Milestone:** token-savings percentage and long-horizon completion rate versus baseline.

### Phase 5 — Benchmark, Demo, Paper (Weeks 20–26)
Freeze the benchmark suite (HABIT-Bench); run all baselines (vanilla agent, AWM-style textual workflows, HABIT); build the split-screen live demo; write the research paper and the college report from the continuously-accumulated notes.
**Targets:** open-source release; paper submission to an agents/LLM-systems workshop (ICLR/NeurIPS workshop track) or ACL demo track; college final evaluation.

### Two process rules (enforced throughout)
1. **Integrate every two weeks.** From week 6 onward, a crude but running end-to-end pipeline must always exist. Layers are never allowed to develop in isolation for a month.
2. **Every phase ends with a number, not a feature.** "Divergence detection works" means nothing; "catches 87% of injected anomalies with 4% false aborts" is progress.

### The demo (what evaluators will see)
A split-screen live dashboard. Left: a vanilla agent processing a stream of 100 tasks — tokens burning, a running cost meter, occasional failures. Right: the same agent wrapped in HABIT. For the first ~10 tasks both sides behave identically (HABIT is learning). Then, visibly, mid-demo, habits kick in: the cost meter on the right flatlines, latency drops ~10x, and the induced workflow appears as a graph with "frozen" (deterministic) nodes and "live" (LLM) nodes in different colors. The showstopper: a deliberately weird task is injected — the audience watches the divergence detector fire, control hand back to the full agent, the task get handled, and the habit recompile. Ninety seconds, and everyone in the room understands the entire thesis.

---

## 5. Work Division — 5 Members

Division is by **layer ownership**: each member fully owns one component end-to-end (design, build, test, measure, document), plus one shared cross-cutting duty. Ownership means: if your layer blocks the pipeline, fixing it is your first priority.

### Member 1 — Team Lead · Architect & Runtime Owner (Layer 4)
**Owns:** the router (matching incoming tasks to habits), divergence detection, fallback/re-inflation, recompile-on-drift, and the overall system architecture and interface definitions.
**Why the lead takes this:** it is the hardest and most novel piece, it touches every other layer, and the leader should sit where the project risk is highest.
**Semester 1:** define all interfaces (Phase 0), build a stub runtime so integration can start early, assist Layer 2 on skeleton design.
**Semester 2:** full divergence detection (schema checks + embedding thresholds, then the XGBoost classifier), fallback state serialization, adversarial-injection experiments.
**Shared duty:** runs the twice-weekly syncs and the bi-weekly integration; maintains the decisions log.

### Member 2 — Instrumentation & SDK Owner (Layer 1)
**Owns:** the trajectory logger, Pydantic schema, storage layer, the LangGraph adapter, and (semester 2) the second framework adapter.
**Profile fit:** the most careful, detail-oriented engineer — this layer's job is to be boring and bulletproof, because everyone else builds on it.
**Semester 1:** callback handlers, schema, SQLite store, 1,000+ trajectories logged per domain.
**Semester 2:** OpenAI Agents SDK adapter; OpenTelemetry alignment; performance hardening.
**Shared duty:** repo infrastructure — CI, packaging, code review standards, release process.

### Member 3 — Compiler Owner (Layer 2)
**Owns:** trajectory clustering, skeleton induction (sequence alignment), LLM-assisted code generation, replay validation harness, DSPy optimization of residual small-model calls.
**Profile fit:** the strongest ML/algorithms person — this is the most algorithmically interesting seat.
**Semester 1:** clustering + alignment + first working crystallizer + replay validation; the headline cost/accuracy table is produced here.
**Semester 2:** smarter variable-step detection, habit versioning, recompilation pipeline.
**Shared duty:** implements and maintains the baselines (vanilla agent, AWM-style textual workflows) so all comparisons stay honest.

### Member 4 — Context Owner (Layer 3) + Workload Engineer
**Owns:** per-step context manifests, paging/prefetch policies, token accounting, the long-horizon experiments — and, in semester 1, the synthetic workload generators and mock tools for all three domains.
**Why this pairing:** the context layer ramps up in semester 2, and building the workloads first teaches this member exactly what context each step touches — perfect sequencing.
**Semester 1:** three workload generators with ground-truth checkers (the project's most important semester-1 artifact after the logger).
**Semester 2:** context manifest induction, paging implementation, the "naive dies / HABIT survives" long-horizon study.
**Shared duty:** dataset/label hygiene — verifies logged trajectories and ground-truth checkers stay correct as the system evolves.

### Member 5 — Evaluation, Benchmark & Demo Owner
**Owns:** HABIT-Bench (the benchmark suite), all measurement scripts and metrics dashboards, the split-screen React demo, and lead authorship of the paper and college report.
**Profile fit:** the best communicator who can also code.
**Authority:** this member defines what counts as success; every other owner must expose the metrics this member demands. Teams that treat evaluation as an afterthought produce demos; teams that give it a dedicated owner produce papers.
**Semester 1:** metric definitions, cost/latency/success measurement pipeline, first dashboard.
**Semester 2:** benchmark freeze, baseline comparisons, Pareto-frontier study, demo app, paper writing.
**Shared duty:** collects every member's weekly "paper duty" hour of written notes into the living draft.

### Team-wide practices
- **Two 30-minute syncs per week:** one for planning, one strictly for blockers.
- **A shared decisions log** so design choices never evaporate.
- **One "paper duty" hour per member per week from semester 1** — the report is accumulated continuously, never written in a panic at the end.
- **Integration owner rotates is NOT allowed** — Member 1 always runs integration, so accountability is unambiguous.

---

## 6. Deliverables

1. **HABIT** — open-source, pip-installable Python library (flight recorder, compiler, context layer, runtime), with LangGraph + one more adapter.
2. **HABIT-Bench** — public benchmark: 3 workflow domains, workload generators, ground-truth checkers, baseline implementations, and the cost–latency–reliability Pareto results.
3. **Live split-screen demo** — the 90-second cost-flatline + divergence-catch demonstration.
4. **Research paper** — submitted to an agents/LLM-systems workshop or demo track; doubles as the college project report.
5. **Documentation** — README, quick-start, architecture deep-dive (the project's public face).

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Crystallizer scoped too ambitiously (trying to compile arbitrary agents) | Restrict scope to tool-call-sequence workflows in 3 structured domains; nail those. Prior work compiled "skills"; our defensible territory is the runtime loop. |
| Divergence detection proves hard; temptation to cut it | Non-negotiable: a compiler without a safety net is a cron job. The fallback loop IS the thesis. Cut a domain or the second adapter instead. |
| Layers developed in isolation drift apart | Bi-weekly forced integration from week 6; interfaces frozen in Phase 0. |
| Groq free-tier rate limits during large experiment runs | Local Ollama models for bulk trajectory generation; Groq reserved for quality-critical runs; cache aggressively. |
| Report/paper written last-minute | Weekly paper-duty hour per member; Member 5 owns the living draft from day one. |

---

*Prepared as the initial project proposal for HABIT. Next documents: the Phase-0 interface specification and the formal college synopsis in the department's required format.*
