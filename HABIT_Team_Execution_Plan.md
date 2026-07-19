# HABIT — Team Execution Plan & Task Breakdown

**Project:** HABIT — Harnessing Agent Behavior Into deterministic Tasks
**Tagline:** *Muscle memory for AI agents. Decide once, execute forever.*
**Team size:** 5 members · Two semesters

This document explains, in simple language, exactly what each of the 5 team members does, in what order the work happens, and gives each person a ready-to-use Claude Code starter prompt. Read the "How the work flows" section first — it explains why the tasks are ordered the way they are.

---

## How the work flows (read this first)

The whole project sits on top of two things: **the trajectory schema** (the exact format we record agent runs in) and **actual recorded trajectories** (real data to work with). Until those two exist, nobody can build their layer correctly. So the first two weeks are a narrow funnel where only 3 people code, and then the work fans out to all 5.

The dependency chain in plain words:

1. **The Lead writes the schema and interfaces first** → this unblocks everyone.
2. **The Recorder and the Workload Generator get built next** → together they produce trajectories (recorded agent runs).
3. **Once trajectories exist**, the Compiler and Context layers can start in parallel.
4. **The Runtime** needs the Compiler to exist (it routes tasks to compiled habits), so it comes slightly later.
5. **Evaluation** touches everything, so that person starts on Day 1 with the Lead (designing what we measure) and finishes last (running all the final comparisons).

**Golden rule:** the schema must be frozen by end of Week 2 and treated as sacred. Changing it later ripples through all four layers and wastes weeks. Version it if absolutely necessary, but resist changes.

---

## The 5 seats at a glance

| Member | Role | Owns (Layer) | Starts | Difficulty |
|---|---|---|---|---|
| **Member 1 (You)** | Lead · Architect · Runtime | Layer 4 — routing, divergence detection, fallback | Day 1 (first) | Highest |
| **Member 2** | Instrumentation & SDK | Layer 1 — recorder, storage, adapters | Day 3 | Medium |
| **Member 3** | Compiler | Layer 2 — clustering, skeleton, codegen, validation | Week 3 | Highest (algorithmic) |
| **Member 4** | Context + Workloads | Layer 3 — memory paging + workload generators | Day 3 | Medium (high ownership) |
| **Member 5** | Evaluation, Benchmark & Demo | Metrics, benchmark, dashboard, paper | Day 1 (with Lead) | Medium (rigor + communication) |

---

# MEMBER 1 — YOU · Lead, Architect & Runtime Owner (Layer 4)

### What you're responsible for, in simple words
You are the brain of the operation in two senses. First, you design the skeleton everyone builds on — the exact data format (schema) and the "contracts" (interfaces) that say how each layer talks to the others. Second, you own the smartest and most novel part of the actual system: the **runtime**. The runtime is the live traffic cop. When a task comes in, it decides: "Is this a task we've done many times before? → run the cheap compiled habit. Is this new or is something going wrong mid-way? → hand it to the full AI agent." That decision-making, and the safety net that catches problems mid-run, is the heart of the whole research contribution.

### Why this seat is yours
It maps directly onto what you already built in ARIA — watching an agent's behaviour and making a judgement about it. Here, instead of diagnosing failure after the fact, you're deciding live whether to trust a habit or fall back to the AI. Same instincts, same skills (LangGraph, DSPy, XGBoost), applied forward instead of backward. You also hold the entire design in your head, which is exactly who should own the interfaces.

### Your tasks

**Semester 1 (foundations + unblock everyone):**
1. Write the trajectory schema together with Member 5 (Week 1) — this is the format for recording every agent run.
2. Write the interface contracts between all four layers in a `docs/decisions.md` file — how does the recorder hand data to the compiler? how does the runtime call a habit? Decide all of this on paper before code.
3. Build a "stub" runtime — a placeholder that, for now, just always calls the live AI agent. This lets the team wire the whole pipeline together in Week 4 even before real habits exist.
4. Help Member 3 shape the compiled habits so your runtime can route to them cleanly.

**Semester 2 (your real research contribution):**
1. **Router:** when a task arrives, match it (using embeddings) to a known habit, or decide it's novel.
2. **Divergence detector:** while a habit runs, watch every step. Start simple and deterministic — check that each tool's output matches the shape we've always seen, and that intermediate results are in the normal range. Later, upgrade to an XGBoost classifier (your ARIA skill) for smarter detection.
3. **Fallback:** when something looks off, safely save the current state, page the right context back in, and hand control to the full AI agent.
4. **Recompile-on-drift:** if the world genuinely changed (a tool's format changed), mark the habit stale and trigger a rebuild.

### Skills you'll use
LangGraph internals, DSPy, XGBoost, FastAPI, systems/architecture thinking.

### Your Claude Code starter prompt
```
Read the attached HABIT_Project_Proposal.md fully before writing any code — it defines the project.

I am the team lead and I own the architecture and the runtime layer (Layer 4). This session is Phase 0: I need to lay the foundation the whole team builds on. Do the following:

1. Scaffold the repo as an installable Python package (package name: habit, Python 3.11+, src/ layout) with folders: src/habit/{schemas, recorder, compiler, context, runtime, adapters, workloads}/, each with __init__.py. Add pyproject.toml, pytest, ruff, and a GitHub Actions CI workflow (lint + test). Add a README.md with the tagline "Muscle memory for AI agents — decide once, execute forever" and an architecture section describing the 4 layers.

2. Define the trajectory schema in src/habit/schemas/trajectory.py using Pydantic v2. Model a Trajectory (id, task_description, domain, started_at, outcome [success/failure/aborted], final_output, steps list, total_tokens, total_cost_usd, model_used) and a Step (index, type [llm_call/tool_call], tool_name, tool_args, tool_result, tool_result_schema_fingerprint, context_keys_read, context_keys_written, latency_ms, tokens_in, tokens_out, cost_usd). Make context access (keys read/written per step) first-class — the context layer depends on it. Add a JSON round-trip test.

3. Write docs/decisions.md defining the interface contracts between the four layers: what the recorder outputs, what the compiler consumes and produces, how the runtime calls a compiled habit, and how fallback hands state back to the live agent. Keep these as clear Python Protocol/ABC stubs in src/habit/interfaces.py.

4. Build a stub runtime in src/habit/runtime/ that implements the routing interface but for now always routes to the live agent (a placeholder). This lets the team integrate end-to-end early.

Rules: keep every module small and typed; write tests alongside code; commit in logical increments; if a decision isn't covered by the proposal, pick the simplest option and record it in docs/decisions.md. When done, summarize the schema, the interfaces, and the commands to run tests.
```

---

# MEMBER 2 — Instrumentation & SDK Owner (Layer 1)

### What they're responsible for, in simple words
This person builds the **flight recorder** — the piece that quietly watches the AI agent do its work and writes down everything it did, in the exact schema the Lead defined. Every step, every tool call, every input and output, gets logged. Their layer has one job: be completely reliable and invisible, because every other layer eats the data it produces. If the recorder is buggy, the whole project gets bad data and nothing downstream works.

### Explain it to them like this
"You're building the black-box flight recorder for AI agents. When the agent runs, you capture a perfect diary of what it did. You're not doing anything clever with the data — the cleverness is downstream — but you are the foundation everyone stands on, so your job is to be rock-solid."

### Their tasks

**Semester 1:**
1. Build a `TrajectoryRecorder` that wraps a LangGraph agent using its callbacks and produces validated Trajectory objects (matching the Lead's schema).
2. Build a SQLite store that saves trajectories and can fetch them by domain and outcome, plus a simple stats function (how many runs, average cost, average steps per domain).
3. Own the repo "plumbing" for the whole project — packaging, CI, code-style (ruff), the release process.
4. Write tests using a *fake* agent so tests run without any API key.
- **Milestone:** 1,000+ trajectories logged per domain.

**Semester 2:**
1. Build a second adapter for the OpenAI Agents SDK — this proves HABIT works across frameworks, which is a headline claim, so it matters.
2. Align the schema with OpenTelemetry conventions (makes the project look production-serious).
3. Performance-harden the recorder.

### Skills they'll use
LangGraph callbacks, Pydantic, SQLite, Python packaging, CI. Good seat for a careful, detail-oriented engineer.

### Their Claude Code starter prompt
```
Read the attached HABIT_Project_Proposal.md and the trajectory schema in src/habit/schemas/trajectory.py before writing code. I own Layer 1 — the flight recorder that logs everything an AI agent does.

Build the following:

1. src/habit/recorder/recorder.py — a TrajectoryRecorder that wraps a LangGraph agent via its callback system and emits validated Trajectory objects exactly matching the existing Pydantic schema. Capture every step: LLM calls and tool calls, with args, results, token counts, latency, and cost. Populate the context_keys_read / context_keys_written fields (the context layer depends on these).

2. src/habit/recorder/store.py — a SQLite store with: insert_trajectory(), query_trajectories(domain, outcome), and a stats() method returning count, average cost, average steps, and success rate per domain.

3. Unit tests in tests/ that use a MOCK agent (a scripted fake LLM) so tests run with no API key. Test that a recorded run round-trips correctly through the schema and the store.

4. Make sure the package's CI (GitHub Actions), ruff config, and pytest setup are working — I own repo infrastructure for the team.

Rules: follow the existing schema exactly (do not change it — ask the lead if something is missing); keep modules small and typed; tests must pass offline; commit in logical increments. When done, show me how to run the tests and print the stats table.
```

---

# MEMBER 3 — Compiler Owner (Layer 2)

### What they're responsible for, in simple words
This is the cleverest algorithmic seat. This person takes the pile of recorded agent runs and finds the **repeating pattern** — "for invoice tasks, the agent always does these same 5 steps in the same order." Then they turn that repeating pattern into real, deterministic Python code (a "habit") that runs almost for free, keeping tiny AI calls only for the one or two steps that genuinely change each time. Crucially, before any habit is allowed to go live, they build a safety check that replays old recorded runs through the new code to confirm it produces the right answers.

### Explain it to them like this
"You're the person who spots that the agent keeps doing the same thing over and over, and you replace that repetitive work with cheap code — but you never trust your generated code until it passes a test that replays real past runs. You produce the project's headline result: 'compiled habits are X times cheaper at the same accuracy.'"

### Their tasks

**Semester 1 (produces the headline result):**
1. Cluster the recorded trajectories so similar tasks group together.
2. Align the runs inside a cluster to find the stable skeleton — which steps are always identical vs. which vary.
3. Generate deterministic Python for the skeleton, sending the variable steps to the small cheap local model (Ollama) instead of the big one.
4. Build the replay-validation harness — auto-generated tests that check a compiled habit against real recorded runs before it's trusted. This is what makes HABIT better than older "just write it in text" approaches, so make it strong.
- **Milestone:** the cost/latency/accuracy table comparing live agent vs. compiled habit.

**Semester 2:**
1. Smarter detection of which steps are variable.
2. Habit versioning and the recompile pipeline.
3. Maintain the "old-style textual workflow" baseline so comparisons stay fair.

### Skills they'll use
sentence-transformers (embeddings), scikit-learn clustering (HDBSCAN), sequence alignment, LLM-assisted code generation, DSPy, pytest. Best for your strongest ML/algorithms person.

### Their Claude Code starter prompt
```
Read the attached HABIT_Project_Proposal.md and the trajectory schema before coding. I own Layer 2 — the compiler that turns repeated agent behavior into cheap deterministic code. There should already be recorded trajectories in the SQLite store; if not, generate some first with scripts/generate_trajectories.py.

Build the following in src/habit/compiler/:

1. cluster.py — load trajectories for a domain, embed each task/step sequence with sentence-transformers, and cluster similar trajectories (HDBSCAN or agglomerative). Return groups of trajectories that represent "the same kind of task."

2. skeleton.py — within a cluster, align the step sequences to extract the stable skeleton: which steps appear identically in (almost) every run, and which steps vary. Output a structured "workflow skeleton" (fixed steps + variable slots).

3. codegen.py — turn a skeleton into an executable Python function: fixed steps become deterministic code, variable steps become small LLM calls routed to a cheap local model (Ollama). The generated habit must match the runtime interface defined in src/habit/interfaces.py.

4. validate.py — a replay-validation harness: before a compiled habit is trusted, auto-generate pytest cases that replay recorded trajectories through the compiled code and confirm the outcomes match. A habit that fails validation is rejected.

5. A script that runs the full pipeline on one domain and prints a comparison: live-agent cost/latency/success vs. compiled-habit cost/latency/success.

Rules: follow the existing schema and interfaces; never let an unvalidated habit be marked usable; keep modules small and typed; write tests. When done, show me the comparison table and how to reproduce it.
```

---

# MEMBER 4 — Context Owner (Layer 3) + Workload Engineer

### What they're responsible for, in simple words
Two jobs, sequenced smartly. In semester 1 they build the **practice tasks** — realistic fake workloads (invoice processing, ticket triage, report generation) with mock tools and an automatic answer-checker, so the whole team has consistent tasks to test on. In semester 2 they build the **memory manager** — the piece that stops the agent from drowning in its own context. It works like a computer's virtual memory: keep on the "desk" only what each step actually needs, file the rest away, and fetch it back just before it's needed.

### Why this pairing is smart
Building the workloads in semester 1 teaches this person exactly what information each step of a task uses — which is precisely the knowledge the memory manager needs in semester 2. They learn the terrain first, then optimize it.

### Explain it to them like this
"First you build the playground everyone tests in — realistic tasks with tools and a way to automatically check if the agent got it right. Then, in semester 2, you solve agent amnesia: agents forget things on long tasks because their memory overflows, and you fix that by managing their memory like an operating system manages RAM and disk."

### Their tasks

**Semester 1 (critical — everyone needs tasks to test on):**
1. Build 3 workload generators: invoice processing, ticket triage, report generation. Each produces varied tasks.
2. Give each a set of mock tools (fake but realistic functions the agent calls).
3. Give each a deterministic ground-truth checker (automatically decides success/failure — no AI judgement needed).
4. Add a knob to inject "weird" tasks (malformed inputs, unknown values) at a set rate — needed later for testing the divergence detector.

**Semester 2:**
1. From recorded runs, work out what context each step actually uses (the "context manifest").
2. Build paging (keep vs. file away) and prefetch (fetch back just in time) using token accounting (tiktoken).
3. Run the key experiment: the same long task with naive full-context (which overflows and fails) vs. HABIT's paged memory (which finishes). The IBM context-overflow finding is your motivating reference here.

### Skills they'll use
Python (task and tool design), tiktoken, SQLite/vector store, paging logic. Best for someone systematic who likes owning a whole subsystem solo.

### Their Claude Code starter prompt
```
Read the attached HABIT_Project_Proposal.md and the trajectory schema before coding. I own Layer 3 (context/memory management) and I also build the synthetic workloads the whole team tests on. Start with the workloads — the team needs them immediately.

Build the following in src/habit/workloads/:

1. invoices.py — a generator for invoice-processing tasks. Include 3 mock tools (extract_invoice_fields, lookup_vendor_db, write_record) and a deterministic ground-truth checker (success = correct record written). Add a parameter to inject "weird" invoices (malformed fields, unknown vendor, foreign currency) at a configurable rate — we need these later for divergence testing.

2. tickets.py — a generator for support-ticket triage tasks with mock tools (classify_ticket, lookup_customer, assign_queue) and a ground-truth checker.

3. reports.py — a generator for report-generation tasks with mock tools (fetch_data, summarize_section, assemble_report) and a ground-truth checker.

Each generator must produce tasks that a LangGraph agent can run, and each checker must decide success/failure with NO LLM involvement (pure code).

Then wire scripts/generate_trajectories.py so it can run any of the three workloads through a minimal LangGraph agent (Groq via env key, plus an --offline flag using a scripted fake LLM so it runs with no key), record everything via the recorder, and print the stats table.

Rules: follow the existing schema; keep the checkers deterministic and code-only; keep modules small and typed; write tests using the offline fake LLM. When done, show me how to generate 50 offline invoice trajectories and print the stats.
```

---

# MEMBER 5 — Evaluation, Benchmark & Demo Owner

### What they're responsible for, in simple words
This person decides **what "success" means** and proves it with numbers. They define every metric (cost per run, speed, success rate, how often a habit is used), build the dashboards that show these live, run the fair comparisons against competitors, build the impressive live demo, and lead the writing of the paper and college report. They start on Day 1 with the Lead because the metrics they need must be built into the schema from the very beginning.

### Why this seat has real power
The difference between a project that produces a flashy demo and one that produces a citable paper is a dedicated evaluation owner. Give this person authority: they define the metrics, and everyone else must expose the numbers they ask for.

### Explain it to them like this
"You're the referee and the storyteller. You decide how we measure whether HABIT actually works, you make sure every experiment produces honest numbers, you build the demo that makes people go 'wow' in 90 seconds, and you lead writing the paper. If your numbers are solid, we have a publishable project. If they're sloppy, we just have a nice-looking toy."

### Their tasks

**Semester 1:**
1. Define the metric set with the Lead and make sure the schema captures all of it.
2. Build the measurement pipeline so every experiment automatically produces cost/latency/success numbers.
3. Build the first dashboard (even simple) so results are visible.

**Semester 2:**
1. Freeze HABIT-Bench — the benchmark suite (the 3 domains + checkers + baselines).
2. Run all baselines fairly: vanilla agent, memory-only, caching-only, and old-style textual-workflow.
3. Build the Pareto-frontier study (cost vs. accuracy trade-off).
4. Build the split-screen live demo: left side vanilla agent burning money, right side HABIT flatlining after it learns, then a weird task injected to show the divergence catch. This is the showstopper.
5. Lead-author the paper and the college report.

### Skills they'll use
Metrics/measurement design, React + Recharts, FastAPI websockets, technical writing. Best for your best communicator who can also code.

### Their Claude Code starter prompt
```
Read the attached HABIT_Project_Proposal.md and the trajectory schema before coding. I own evaluation, the benchmark, the dashboard, and the demo. My job is to make sure every experiment produces honest numbers and to build the demo that shows HABIT working.

Build the following:

1. src/habit/eval/metrics.py — functions that take Trajectory objects (or batches) and compute: cost per run, average latency, success rate (using the workload ground-truth checkers), tokens per run, and — once habits exist — habit-hit-rate (fraction of tasks served by a compiled habit vs. the live agent). Confirm the schema exposes everything these need; if a field is missing, list it for the lead.

2. src/habit/eval/compare.py — a harness that runs the SAME set of tasks two ways (live agent vs. HABIT, and later memory-only / caching-only baselines) and produces a comparison table of the metrics above.

3. A simple dashboard (start with a FastAPI endpoint + a minimal React/Recharts page, or Streamlit if faster) that reads results and shows cost, latency, success rate, and habit-hit-rate as live charts.

4. Sketch the structure for the "split-screen demo": left panel runs a vanilla agent over a stream of tasks with a live cost meter; right panel runs the same agent wrapped in HABIT. Stub the layout now; we'll wire real data as the runtime matures.

Rules: metrics must be honest and reproducible; use the workload checkers for success (no LLM-as-judge for correctness); keep it simple first. When done, show me a sample comparison table and how to launch the dashboard.
```

---

## The first 6 weeks — who does what, when

**Weeks 1–2 (the funnel — only 3 people coding):**
- You (Member 1) + Member 5: freeze the trajectory schema and the metric set together.
- You (Member 1): write the layer interfaces in `docs/decisions.md` and build the stub runtime.
- Members 2, 3, 4: read the four key papers (Skill-DisCo, AWM/Trace2Skill, Compiled AI, AFlow) and each write a half-page "their gap vs. ours" — this becomes the related-work section for free.

**Week 3 (first fan-out):**
- Member 2: starts the recorder (schema now exists).
- Member 4: starts the invoice workload generator.

**Week 4 (first integration):**
- Recorder + workload + stub runtime wired together → first real trajectories appear.
- Member 3: starts clustering on the first ~200 trajectories.
- Member 5: stands up the first metrics dashboard.

**Weeks 5–6 (momentum + first checkpoint):**
- 1,000+ trajectories per domain logged.
- Member 3: first crude compiled habit; replay-validation catches its mistakes.
- Member 5: measures habit vs. live cost — the first real number.
- **First bi-weekly integration checkpoint:** a rough end-to-end pipeline must run, even if ugly.

---

## Two rules to enforce as leader

1. **Freeze the schema by end of Week 2 and protect it.** Schema churn is the number one way a 5-person team wastes a month, because every change ripples through all four layers.

2. **Protect the divergence-detection work (your seat) from being cut.** When the middle of semester 2 gets stressful, someone will suggest "let's just always run the compiled path and skip the fallback." Do not agree — a compiler without a safety net is just a cron job, and the fallback loop is exactly what makes HABIT a paper instead of a script. If time gets tight, cut a third domain, or the second adapter, or learned context policies — not the fallback.

---

## Team-wide working practices

- Two 30-minute syncs per week: one for planning, one only for blockers.
- A shared decisions log so design choices never get forgotten.
- One "paper-writing hour" per member per week from semester 1 — the report is built up continuously, never crammed at the end.
- Member 1 always runs the bi-weekly integration, so accountability is unambiguous.

---

*Hand each member their section plus their starter prompt. Attach HABIT_Project_Proposal.md when using any prompt in Claude Code. Run the Lead's prompt first (it creates the schema and repo everyone else depends on), then Members 2 and 4, then Member 3, with Member 5 building metrics alongside from the start.*
