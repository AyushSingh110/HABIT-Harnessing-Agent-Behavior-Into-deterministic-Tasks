# HABIT — The Complete Guide (for anyone, even non-technical)

*Read this top to bottom and you will understand the whole project: what it is, why it exists, how
every part works, which file does what, how we store and measure things, what we use, what we are
trying to do, and what we are NOT trying to do. Simple language throughout. Technical words are
explained the first time they appear.*

---

## Part 0 — Two words you need first

- **LLM / AI model:** the "brain" — a large AI (like the models behind ChatGPT) that reads text and
  writes an answer. It is smart but **slow and expensive**: every time you use it, it costs money and
  takes time.
- **Agent:** a program that uses the AI model to *do a job in steps* — read something, call a tool
  (like a database or a calculator), think again, call another tool, and finish. A "tool" is just a
  normal function the agent can call (look up a customer, check a total, send a reply).

That's all you need. Now the project.

---

## Part 1 — What is HABIT, in one breath?

AI agents are wasteful. To do a job, an agent asks the expensive AI model **at every single step** —
even when it has already done the exact same kind of job a thousand times before. It never learns from
its own past.

**HABIT watches an agent work, learns the parts it does the same way every time, and turns those parts
into ordinary cheap code** that runs **without** the AI model. It calls the full AI back **only** when
something genuinely new or wrong happens.

The tagline: **"Muscle memory for AI agents — decide once, execute forever."**

**The simple picture:** a new employee thinks hard about every task on day one. After doing the same
task a thousand times, they do it fast, on autopilot, and only stop to think when something unusual
shows up. HABIT gives an AI agent that same autopilot.

---

## Part 2 — The problem we are solving (with a real example)

Imagine a company that gets **refund-request** support tickets — hundreds a day. For every refund
ticket, the agent does the same steps:
1. read the message, 2. find the customer, 3. find the last payment, 4. check the refund policy,
5. issue or decline, 6. send a confirmation.

Today the agent calls the expensive AI at *every* one of those steps, every time — even though steps
2–6 are the same boring steps it has done thousands of times. This causes three problems:

- **Cost** — every step is a paid AI call. Hundreds of thousands of tickets a month = a huge bill.
- **Reliability** — the AI is not 100% correct. A task with many AI steps can fail partway through.
- **Memory overflow** — the agent piles everything into its limited "working memory" (its *context
  window*) and on long tasks it forgets its own goal.

All three come from one root cause: **the agent re-does work it already knows how to do, and nothing in
the system learns from its history.** HABIT fixes that root cause.

---

## Part 3 — Our ideology: what we ARE and are NOT trying to do

This matters, so it's up front.

**What we ARE trying to do:**
- Learn an agent's **repeated** behaviour from its own recorded runs and turn it into cheap,
  **deterministic** code (deterministic = same input always gives the same output, no randomness).
- Keep a **safety net**: if a shortcut goes wrong, immediately hand control back to the full AI.
- Learn **what each step needs to remember**, so memory never overflows — and couple this to the
  compiled shortcut (this link is our most novel idea).
- **Prove** it with numbers: cost, speed, correctness.

**What we are NOT trying to do (important — say this honestly):**
- We are **not** magically turning *all* AI reasoning into code. Only the **mechanical, repeated** steps
  become code. Genuine judgement (e.g. "read this contract and decide if it creates liability") still
  needs the AI. In our test domains every step is mechanical, so our shortcuts are 100% AI-free — but
  that is because we chose clean domains, not because reasoning was "compiled away."
- We are **not** (yet) claiming we make agents *more reliable* with evidence. In our tests the tools
  never fail, so both the agent and the shortcut score 100%. The reliability benefit is a **theory**
  for now, not a measured result. (The cost/speed benefit **is** measured and real.)
- We are **not** using a real company's private data — we **generate** realistic synthetic tasks so we
  can check answers with plain code and run everything for free.

---

## Part 4 — The four layers (the heart of the system)

HABIT is built as **four layers**, each with its own folder in the code. Think of them as four stages:
**watch → learn → remember → run safely.**

Below, for each layer: a simple explanation, then the exact files and what each one does.

---

### LAYER 1 — The Recorder ("the flight recorder") — folder `src/habit/recorder/`, `src/habit/schemas/`, `src/habit/storage/`, `src/habit/adapters/`

**Simple:** this layer watches the agent and writes down everything it does as a neat diary entry.

**Analogy:** a CCTV camera + a logbook for one job.

**What it records (one "diary entry" = one `Trajectory`):** the task, every step, every tool called
(with its inputs and outputs), what information each step looked at, how many tokens the AI used, the
timing, and whether the final answer was correct.

**The files:**
- `schemas/trajectory.py` — **the shape of the diary entry.** It defines, using a library called
  **Pydantic** (which checks data is valid), exactly what a `Trajectory` contains: the steps, the tool
  calls, the context, the outcome. This file is **frozen** — nobody is allowed to change it without
  approval, because every other layer depends on it.
- `schemas/fingerprint.py` — makes a **"fingerprint" of a tool's result shape.** It hashes the *keys
  and types* of a result (not the values). So two invoices with different totals get the **same**
  fingerprint, but a result that suddenly has an extra or missing field gets a **different** one. This
  fingerprint is how Layer 4 later notices "something changed."
- `recorder/recorder.py` — **the actual recorder.** You call `start_run(...)`, then `record_llm_call`
  / `record_tool_call` / `record_other` for each step, then `finish(...)`. It numbers the steps in
  order, fixes all timestamps to one time zone (UTC), computes the fingerprint, and saves the finished
  diary entry.
- `adapters/langgraph.py` — **the plug for a real agent.** LangGraph (a popular framework for building
  agents) fires little "events" whenever the agent does something; this file listens to those events
  (`on_llm_end`, `on_tool_end`) and records one step per event. *This is how we know which step the
  agent took — the framework tells us.*
- `storage/models.py` + `storage/store.py` — **where the diary is kept** (see Part 5).

**How we know *which* step the agent took:** two ways. For our test agents (which we wrote ourselves),
we record each step explicitly because we know the workflow. For a real LangGraph agent, the framework
emits an event per action and the adapter records it. We never guess.

---

### LAYER 2 — The Compiler ("turns the recipe into cheap code") — folder `src/habit/compiler/`

**Simple:** this layer reads thousands of diary entries, finds the repeated recipe, and turns it into a
cheap shortcut that runs without the AI. It only happens offline (in the background), not live.

**Analogy:** after watching an experienced worker do the same job 1000 times, you write down the exact
checklist they follow — and from then on anyone can follow the checklist instead of thinking it through.

**It works in four steps, one file each:**
- `clustering.py` — **group the runs that follow the same recipe.** It builds a "structural signature"
  = the exact ordered list of (step type, tool name) for a run, and groups runs with an identical
  signature. (Simple and exact — not fancy AI similarity. On our data this cleanly gives one group per
  job type.)
- `skeleton.py` — **find what's stable.** For each position in the recipe, it checks what is the same
  across every run (which information the step read, and the shape of the tool's result). A step whose
  result-shape is always the same is marked "stable."
- `crystallizer.py` — **build the shortcut (the "habit").** This is the clever part. For each tool's
  input and for the final answer, it figures out **where the value comes from** by matching recorded
  values across runs: does it come from the task's input, or from a field of an earlier tool's result?
  The answer becomes a **plan** (`HabitPlan`). A small "interpreter" called `run_habit` then executes
  that plan — it fills in each input from the right place, calls the tools in order, and assembles the
  answer — **with no AI calls and no risky code generation.** (We do **not** ask an AI to write Python,
  and we do **not** run generated code strings. We run a safe, fixed plan.)
- `validation.py` — **check the shortcut before trusting it.** It splits the runs into "practice" and
  "held-back." It builds the shortcut from the practice runs, then re-runs it on the held-back runs and
  requires it to produce the **correct** answer every time. Only then is the shortcut marked **usable**.
  A broken shortcut is rejected. *This is our safety guarantee: a shortcut that hasn't passed this test
  is never used.*

---

### LAYER 3 — The Context layer ("learns what to remember") — folder `src/habit/context/` — **our most original idea**

**Simple:** this layer learns, for each step, **which pieces of information that step actually needs**,
so the agent keeps only those and throws away the rest. This stops the "memory overflow" problem.

**Analogy:** an operating system deciding what stays in fast memory (RAM) and what gets put away on disk
— but learned from watching which papers a worker actually picks up at each step.

**The files:**
- `policy.py` — **learn the keep/throw-away rule.** Using the recorded "what each step read" data, it
  computes, for each step, which items are still needed now or later ("live") and which are never read
  again ("evictable" = safe to drop). This is called **liveness analysis** (a classic idea borrowed
  from how compilers manage computer registers).
- `paging.py` — **measure the benefit.** It simulates the memory window over a whole task: the naive
  way (keep everything) grows and grows; our policy (keep only what's live) stays small. It reports how
  much smaller the window is, and whether it stays under a memory budget ("survives") or overflows
  ("dies").
- `validation.py` — **prove the rule is safe.** It checks on held-back runs that the policy never threw
  away something a step later needed (a "starvation"). The policy is only trusted if there are **zero**
  starvations. (This is the memory version of Layer 2's safety check.)

**Why this is the special part:** other systems either compile behaviour **or** manage memory, and
memory systems usually ask the AI at runtime what to keep. **We learn the memory rule from the same
recordings that build the shortcut, and we prove it's safe.** Linking the two — the compiler telling the
memory system what each step needs — is what no other project does.

---

### LAYER 4 — The Runtime ("the live traffic controller + safety net") — folder `src/habit/runtime/`

**Simple:** this is the always-on part. When a real task arrives, it decides: use the cheap shortcut, or
the full AI? It watches the shortcut, and if anything looks wrong, it instantly switches to the full AI.

**The files:**
- `router.py` — **the decision-maker.** It holds the **usable** shortcuts (only validated ones) and,
  for an incoming task, returns the shortcut if one applies, or "none" (meaning: use the full AI). It
  also checks the task actually has the inputs the shortcut needs.
- `divergence.py` — **the "is it going off-script?" watcher.** While the shortcut runs, after each tool
  call it compares that tool's result **fingerprint** (shape) to what it learned to expect. If the shape
  is different (or the shortcut fails to run), that's "divergence" — a signal to stop trusting the
  shortcut.
- `loop.py` — **the whole live loop.** For a task it does: ask the router → run the watched shortcut →
  if clean, return the cheap answer (mode "habit") → if it went off-script, run the full AI instead
  (mode "fallback") → if there was no shortcut, run the full AI (mode "live"). This is the safety net
  in action.
- `drift.py` — **the "has the world changed?" monitor.** If shortcuts keep failing and falling back a
  lot, the world has probably changed (e.g. a tool now returns a new format); it flags this so we can
  **recompile** a fresh shortcut from new recordings.

**One honest detail:** when a shortcut goes wrong, we **re-run the whole task with the full AI** (we do
not try to resume the shortcut from the middle). For our tasks this is correct and simple.

---

## Part 5 — How a trajectory is measured, captured, and stored (step by step)

The user asked specifically about this, so here it is in detail but simply.

**What is captured for one run (the Trajectory):**
- the task and its inputs; a unique `trajectory_id`;
- every **step** in order, each tagged as an AI step, a tool step, or other;
- for an AI step: the model name and the **tokens used** (input tokens + output tokens) — *this is how
  we measure cost*;
- for a tool step: the tool name, its inputs, its output, and the output's **fingerprint**;
- for every step: **what information was available** and **what it actually read** — *this is the data
  Layer 3 learns from*;
- start and end **timestamps** for timing;
- the final answer and a **correct/incorrect** label.

**How "correct" is decided:** every task type ships a **ground-truth checker** — a plain Python function
(never an AI) that checks the answer exactly (e.g. the invoice checker verifies the total, the vendor,
the validity flag). Its result is stored as `ground_truth_match`. *We never ask an AI "is this right?"*

**How cost and latency (time) are measured:**
- **Number of AI calls** = count of AI steps in the diary. (A shortcut makes zero.)
- **Tokens** = add up the input+output tokens over the AI steps. For our offline "fake" model these are
  made-up; for the **real** models (Groq, Ollama) they are the true counts the service reports.
- **Latency (wall-clock time)** = we wrap each task in a stopwatch (`time.perf_counter`) inside the
  benchmark and record the milliseconds. Each step also stores its own start/end time.

**Where it is stored:**
- In a **database**, through the files `storage/store.py` and `storage/models.py`.
- The database technology is **SQLAlchemy** (a Python library that talks to databases) on top of
  **SQLite** by default — SQLite is a tiny database that lives in a single file, `habit.db`, with zero
  setup. (It can switch to **PostgreSQL**, a bigger database, just by changing one setting —
  `DATABASE_URL` — with no code change.)
- There is **one table**, called `trajectories`. Each row = one run. The whole diary entry is saved as
  a **JSON blob** in a `payload` column (so nothing is lost), plus a few separate columns
  (`domain`, `success`, `started_at`) that are copies used only to search/filter quickly.
- **Important honest note:** the *shortcuts (habits) themselves are NOT stored in a database* — they
  live in the computer's memory while the program runs. Saving/versioning them in a database is a
  planned future step, not built yet.

---

## Part 6 — The complete pipeline (the whole story, start to finish)

Here is everything joined up, as a story, for the refund-ticket example:

1. **A task arrives** and the **full AI agent** handles it, doing all the steps.
2. **The Recorder** (`recorder/recorder.py`) writes the run as a `Trajectory` and **saves it** to the
   database (`storage/`). The **checker** marks it correct or not.
3. We repeat this ~1000 times (via `scripts/generate_corpus.py`) → a big pile of recordings in
   `habit.db`.
4. **Offline, the Compiler** (`compiler/`) runs: **group** the identical recipes (`clustering.py`) →
   **find the stable recipe** (`skeleton.py`) → **build the shortcut plan** (`crystallizer.py`) →
   **test it on held-back runs** (`validation.py`). If it passes, the shortcut is **usable**.
5. **The Context layer** (`context/`) learns the memory rule for that recipe and **proves it safe**.
6. **A new ticket arrives live.** The **Runtime** (`runtime/`) kicks in: the **router** sees a usable
   shortcut exists → runs it with **zero AI calls** → the **divergence watcher** checks each step → all
   normal → returns the answer in a fraction of a millisecond.
7. **A weird ticket arrives** (a tool returns a new shape). The **divergence watcher** notices → the
   **loop** falls back to the **full AI**, which handles it correctly. That new run is **recorded**
   again.
8. If shortcuts keep failing (the world changed), the **drift monitor** flags it and we **recompile** a
   fresh shortcut from the new recordings. The system keeps improving by itself.

---

## Part 7 — How we know it actually works (testing and measuring)

Three independent ways we check correctness:

1. **Automated tests — 199 of them.** Every piece has tests (in the `tests/` folder) that run offline
   (no internet, no API key) and must pass. We also use **mypy** (checks the code's types are correct)
   and **ruff** (checks code style). All green.
2. **Ground-truth checkers.** For every task, plain-code checkers verify the final answer exactly. The
   shortcut is only trusted if it reproduces the correct answers on **held-back** runs it never
   practised on. We even checked it works on **brand-new, unseen** tasks (150 out of 150 correct) — so
   it genuinely learned the recipe, not just memorised examples.
3. **The benchmark + real models.** We run the live agent vs the shortcut on fresh tasks and measure
   cost, tokens, time, and success (`eval/benchmark.py`, `scripts/run_benchmark.py`). We ran it on
   **real** models (Groq's `gpt-oss-20b`, and local Ollama `qwen3:8b` and `llama3.1:8b`). Every time:
   the shortcut matched the agent's correct answer with **0 AI calls, 0 tokens, sub-millisecond time**,
   versus the live agent's 5–6 AI calls and seconds-to-minutes per task.

We also made **figures** (`scripts/make_figures.py` → the `figures/` folder) showing: cost by strategy,
the memory window staying flat while the naive one grows, the shortcut working on shifted data, and the
detector's catch-rate.

---

## Part 8 — What we have built, and what we have NOT (the honest status)

**Built and working (tested):**
- All four layers (recorder, compiler, context, runtime) + the evaluation tools.
- Three realistic task types (invoice processing, support-ticket triage, report generation) with
  automatic answer-checkers.
- A 3,000-run recorded dataset.
- Real cost measurements on real AI models.
- Figures and two bonus findings (the shortcut still works on shifted data; the memory rule stays safe
  on shifted data).

**NOT built yet (planned / future):**
- Saving shortcuts in a database (they're in memory now).
- A smarter "wrong value, same shape" detector (our current detector catches shape changes, not value
  changes).
- A fancy AI-similarity grouping (we use exact matching, which is enough for our clean data).
- A second agent-framework plug-in; a live split-screen **demo website** (FastAPI + React).
- A measured **reliability** improvement (it's currently theory; our tools don't fail).
- Automatic token-size measurement with a library called tiktoken (we pass sizes in for now).

---

## Part 9 — What libraries (tools) we use, and why

| Library | What it is | Why we use it | Used now? |
|---|---|---|---|
| **Python 3.11+** | the programming language | the whole AI ecosystem is Python | Yes |
| **Pydantic v2** | checks data has the right shape | guarantees every trajectory is valid | Yes |
| **SQLAlchemy 2.x** | talks to databases in Python | store trajectories; switch SQLite↔Postgres with one setting | Yes |
| **SQLite** | a tiny file-based database | zero setup; `habit.db` | Yes |
| **LangGraph / langchain-core** | a framework for building agents | plug the recorder into a real agent | Yes (optional) |
| **Groq** | fast cloud AI models | real cost/speed numbers | Yes (optional) |
| **Ollama** | run AI models locally for free | real numbers without rate limits | Yes (optional) |
| **matplotlib** | makes charts | the research figures | Yes (for figures) |
| **pytest / mypy / ruff** | testing, type-checking, style | keep the code correct and clean | Yes |
| scikit-learn, HDBSCAN, sentence-transformers | AI similarity/clustering | *proposed, not used* (we use exact matching) | No |
| XGBoost | a machine-learning classifier | *proposed* for the smarter detector | No |
| tiktoken | counts tokens | *proposed* for real memory sizing | No |
| FastAPI + React | web backend + frontend | *proposed* for the demo website | No |

Total cost to run everything: **₹0** — every piece is free or local.

---

## Part 10 — A tiny glossary (the technical words, explained simply)

- **Agent** — a program that uses the AI to do a job in steps, calling tools.
- **Tool** — a normal function the agent can call (database lookup, calculator, send email).
- **Trajectory** — the complete recorded diary of one run.
- **Context window** — the agent's limited working memory (like a small desk).
- **Deterministic** — always gives the same output for the same input; no randomness.
- **Habit** — our compiled shortcut: a fixed plan that runs the recipe without the AI.
- **Cluster** — a group of runs that followed the same recipe.
- **Skeleton** — the stable common recipe extracted from a cluster.
- **Provenance** — where a value comes from (the task input, or an earlier result).
- **Replay validation** — re-running a shortcut on past runs to prove it's correct before trusting it.
- **Fingerprint** — a hash of a result's *shape* (keys/types), used to spot changes.
- **Divergence** — when a running shortcut goes off-script (a result's shape is unexpected).
- **Fallback** — switching from the shortcut back to the full AI.
- **Liveness / eviction** — keeping information a step still needs, dropping what it never reads again.
- **Drift** — the world changed, so the old shortcut keeps failing and must be recompiled.
- **Token** — a piece of a word; AI cost is measured in tokens.
- **Ground-truth checker** — plain code that decides if an answer is correct (never an AI).

---

## Part 11 — If you remember only five things

1. **The idea:** agents redo known work every time; HABIT learns the repeated recipe and runs it as
   cheap code, waking the full AI only for new or wrong situations.
2. **The four layers:** Recorder (watch) → Compiler (learn the recipe) → Context (learn what to
   remember) → Runtime (run it live with a safety net).
3. **The proof:** on real AI models, the shortcut matches the agent's correct answers with **zero AI
   calls and zero tokens** — fully built and tested (199 tests).
4. **The novelty:** we learn the **memory rule from the same recordings** that build the shortcut, and
   we **prove it safe** — nobody else links the compiler to memory like this.
5. **The honesty:** it's synthetic data; the cost win is measured and real; the reliability win is still
   theory; and we only compile the mechanical steps, never genuine reasoning.
