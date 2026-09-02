# HABIT — How It Actually Works (internal mechanisms)

*The concrete approach inside each layer: how we record a run, how we know which step the agent took,
how we know an output was wrong (and keep that out of what the compiler trusts), how we capture cost
and latency, and how everything is stored. Written as the engineering guide and the paper's Method
section. Last updated: 2026-09-01.*

---

## 0. The one object everything revolves around: the Trajectory

Everything HABIT does is built on one structured record — the **Trajectory** (Pydantic v2, frozen,
in `habit.schemas`). One Trajectory = one run of one task. It holds:

- `trajectory_id`, `domain`, `task_type`, `task_input` (the task), `metadata`, `started_at`, `ended_at`.
- `context_items`: the list of information pieces that appeared during the run (each a `ContextItem`
  with an `item_id`, a `kind`, and which step produced it).
- `steps`: an ordered list of `Step`. Each `Step` records:
  - `step_index` (0,1,2… in order), `step_type` = `LLM_CALL` / `TOOL_CALL` / `OTHER`.
  - for an LLM step: `llm_call` = `LLMCall(provider, model, input_tokens, output_tokens)` — **this is
    where cost is captured**.
  - for a tool step: `tool_call` = `ToolCall(tool_name, call_id, arguments, result, error)`.
  - `tool_result_schema_fingerprint`: a hash of the tool result's **shape** (keys + types) — **this is
    the divergence signal**.
  - `context_available` and `context_reads`: which context items were present, and which this step
    actually **read** — **this is the data Layer 3 learns from**.
  - `started_at`, `ended_at` (timezone-aware) — per-step timing.
- `outcome`: `Outcome(success, final_output, error, ground_truth_match)` — **`ground_truth_match` is the
  correct/wrong label**.

The schema enforces its own rules (a TOOL step must have a tool_call; the fingerprint must be present
exactly when there's a tool result; `context_reads` must be a subset of `context_available`; every
referenced item_id must exist in `context_items`; timestamps must be timezone-aware). So a malformed
record is rejected immediately, not stored as garbage.

**Where this comes from:** `habit.recorder.TrajectoryRecorder`. You call `start_run(...)` to get a
`RunRecorder`, then `record_llm_call(...)`, `record_tool_call(...)`, `record_other(...)` as the run
proceeds, then `finish(...)`. The recorder auto-numbers steps, normalizes all timestamps to UTC,
computes the fingerprint internally, and saves the finished Trajectory to storage.

---

## 1. Layer 1 — Recording: how we know which step the agent took

There are **two ways** we capture a run, and both produce the same Trajectory object.

### (a) The framework adapter (a real agent) — `habit.adapters`
For a real LangGraph/LangChain agent we do **not** guess the steps — the framework *tells* us. Our
`HabitCallbackHandler` subscribes to LangChain's callbacks, which fire on every action the agent takes:
- `on_chat_model_start` / `on_llm_end` → an **LLM step** (we read the model name and the real token
  usage from the response).
- `on_tool_start` / `on_tool_end` → a **tool step** (we read the tool name, its arguments, and its
  returned result).

Each event carries a `run_id`; the handler pairs each `start` with its matching `end` by `run_id`, so
even if steps interleave we attribute each one correctly. When an end-event fires, the handler calls
the corresponding recorder method. *That is how we know exactly which step the agent took: the agent
framework emits an event per action, and we record one Step per event.*

### (b) The authored baseline agent — `habit.baseline`
For our synthetic experiments we use an **authored** agent per domain (e.g. `run_invoice_baseline`).
Because *we wrote the workflow*, we know each step by construction — we call `record_tool_call` /
`record_llm_call` explicitly at each step via a small helper, `BaselineTrace`. This is a deliberate
choice: it lets us capture **faithful `context_reads`** (what each step actually used), which the
callback adapter can't infer — and Layer 3 depends on that data.

`BaselineTrace` also keeps the bookkeeping correct for every agent: it maintains the growing set of
available context items, snapshots `context_available` at each step, records the exact `context_reads`
the step used, computes the fingerprint (inside `record_tool_call`), and auto-assigns `step_index`.

### How the fingerprint (the "shape" of a result) is captured
`schema_fingerprint(value)` (in `habit.schemas`) walks a value and produces a **value-independent** hash
of its structure: `{"total": int, "lines": [ {"sku": str} ]}` hashes the *keys and types*, not the
numbers. So two invoices with different totals get the **same** fingerprint, but an invoice whose tool
suddenly returns an extra/missing field gets a **different** one. The recorder computes this for every
tool result and stores it on the step. This is what the divergence detector later checks against.

---

## 2. How we know an output was WRONG — and keep it out of what the compiler trusts

This is a core design rule: **ground-truth is decided by pure code, never by an LLM.**

- Every workload domain ships a **ground-truth checker** — an ordinary Python function
  `checker(task, final_output) -> bool` (e.g. the invoice checker verifies the extracted total,
  vendor, `totals_valid`, etc. exactly). No model is asked "is this right?".
- When a run finishes, we call the checker and store the result in `outcome.ground_truth_match`
  (`True` = the run produced the correct answer, `False` = it did not).

**How the compiler avoids learning a wrong output as if it were correct:** the compiler never *trusts*
a habit until it passes the **replay-validation gate** (`validate_habit`, `habit.compiler`). That gate:
1. considers **only** trajectories whose `ground_truth_match is True` (wrong runs are skipped — they
   are not something a good habit should reproduce), and
2. re-runs the compiled habit on those held-out correct runs and requires its output to **equal the
   recorded correct output** on every one.

A `CompiledHabit` is marked `usable` **only if** that gate passes (it's a read-only property tied to
the validation result, so "usable" can't be set independently). So even if a wrong run slipped into the
training set, a habit is only ever used if it reproduces the **correct** outputs on held-out runs —
a wrong output can never become the thing the habit is trusted to imitate. The runtime router
(`build_router`) then admits **only usable habits** to serve traffic.

---

## 3. How we capture COST and LATENCY (and time-per-answer)

Three quantities, each captured at a specific place:

- **Number of LLM calls per task** — just the count of `LLM_CALL` steps in the Trajectory. (A habit
  makes zero, structurally: it has no LLM steps.)
- **Tokens per task** — every `LLMCall` step stores `input_tokens` and `output_tokens`. These come
  from the model itself: our `LargeModel.complete(prompt)` returns an `LLMResponse(text, input_tokens,
  output_tokens)`. For `FakeModel` (offline) these are synthetic; for `GroqModel` / `OllamaModel` they
  are the **real** counts the API/engine reports (`usage.prompt_tokens` / `usage.completion_tokens` for
  Groq, `prompt_eval_count` / `eval_count` for Ollama). Cost = tokens summed over the LLM steps.
- **Latency (wall-clock time per task)** — measured in the benchmark (`habit.eval.run_benchmark`) by
  wrapping each task's execution in `time.perf_counter()` and recording the elapsed milliseconds. Every
  step also stores its own `started_at`/`ended_at`, so per-step timing is available too.

`run_benchmark` runs the **live agent** and the **compiled habit** on the same fresh (unseen) tasks and
aggregates, per domain: `success_rate` (from `ground_truth_match`), `mean_llm_calls`, `mean_tokens`,
`mean_latency_ms`. That's how we produce the headline table. To get real rupee/latency numbers we simply
pass a real model (`--model groq` or `--model ollama`); the habit's side stays 0 by construction. (For
efficiency, training/compilation can use the cheap `FakeModel` while only the live-cost measurement uses
the real model — habits are model-independent, so this is sound.)

---

## 4. How everything is STORED — `habit.storage`

Trajectories are persisted through the `TrajectoryStore` interface, implemented on **SQLAlchemy 2.x**
(`SqlAlchemyTrajectoryStore`). Design:
- The whole Trajectory is serialized to a **JSON payload column** (`trajectory.model_dump(mode="json")`),
  and read back losslessly with `Trajectory.model_validate(row.payload)` — so no field is ever lost or
  mangled, and timezone-aware timestamps survive.
- Alongside the payload we keep **indexed scalar columns** — `trajectory_id` (primary key), `domain`,
  `task_type`, `success`, `started_at` — purely so queries/filters are fast (`query(domain=…, success=…)`
  orders by `started_at`).
- The backend is chosen **only** by the `DATABASE_URL` environment variable: SQLite by default
  (`sqlite:///habit.db`), PostgreSQL by changing that one variable — no code change, no backend-specific
  SQL. The 3,000-trajectory corpus lives in `habit.db`.

---

## 5. Layer 2 — Compiler: how a habit is built from the records

Four steps, all deterministic and offline (`habit.compiler`):

1. **Cluster** (`cluster_trajectories`): group runs that follow the same recipe. The key is the
   **structural signature** — the ordered tuple of `(step_type, tool_name)` across the steps. Runs with
   an identical signature are one cluster. (On our data this recovers one cluster per domain, purity 1.0.)
2. **Induce the skeleton** (`induce_skeleton`): for each step position across the cluster, record what
   is **stable** — the common `context_reads`, and the common `tool_result_schema_fingerprint`. A step
   is flagged `stable` only if it's a deterministic tool step whose reads and result-shape are identical
   across every run. (This is what tells Layer 4 which steps have a checkable fixed shape.)
3. **Crystallize** (`crystallize` → a `HabitPlan`): the interesting part — **automatic provenance
   induction**. For each tool argument and each final-output field, we find where its value comes from by
   **matching recorded values across the cluster** to the task input or a prior tool result. The first
   consistent source (in priority order: an input field → the whole input → a prior result's field → a
   whole prior result → a constant) becomes that argument's `Source`. The result is a `HabitPlan`:
   the ordered tool steps, each with `arg_sources`, plus an `output_assembly`. It is executed by a
   **pure interpreter**, `run_habit(plan, task_input, tools)` — no LLM, no `eval`/`exec` of generated
   code — which computes each argument from its Source, calls the tools in order, and assembles the
   output. (Verified to reproduce correct outputs on **unseen** tasks — it captured the *structure*, not
   memorized values.)
4. **Replay-validate** (`compile_habit` + `validate_habit`): split the cluster into train/held-out,
   crystallize on train, and require the habit to reproduce the correct output on every held-out run
   (see §2). Only then is it `usable`.

---

## 6. Layer 3 — Context policies: how we learn what to keep in memory

The novelty. From the recorded `context_reads` / `context_available`, we compute a per-step memory
policy by **liveness analysis** (`habit.context`, `induce_context_policy`):
- Across the cluster, for each step position, take the union of items **read** and items **available**.
- Compute, for each item, the **last step that reads it** (`last_read`).
- At step *i*: an item is **live** if it is read now or later (`last_read >= i`); an item that is present
  but never read again is **evictable**. The policy = keep the live items, drop the evictable ones.

Then:
- **Paging** (`simulate_paging`): given per-item token sizes, compute the window token load at each step
  for the naive "keep everything" strategy vs. the policy "keep only live", plus peaks; `survives(budget)`
  says whether each stays under a token budget. (Long-horizon result: naive grows to *n* items, the
  policy stays at ~2, 90–98% savings, naive "dies" at a budget while the policy "survives".)
- **Safety gate** (`validate_context_policy` / `induce_and_validate_policy`): induce the policy on a
  train split, then on **held-out** runs check that every item a step reads is in that step's `live` set.
  A read of an evicted item = a "starvation". The policy is `safe` only if there are **zero** starvations
  on held-out runs — the memory analog of the Layer-2 replay gate. (Holds even on the shifted split.)

---

## 7. Layer 4 — Runtime loop: routing, catching mistakes, falling back, recompiling

The always-on part (`habit.runtime`):

- **Router** (`build_router`, `Router.route`): admits **only usable habits**, keyed by domain. For an
  incoming task it returns the habit's plan **iff** a usable habit exists for that domain and the task
  supplies every input field the plan needs; otherwise `None` = "run the live agent".
- **Divergence detector** (`run_habit_checked`): runs the habit under monitoring. It wraps the tools so
  each real result is recorded in call order, runs the **same** `run_habit` interpreter, then compares
  each tool result's `schema_fingerprint` to the skeleton's expected fingerprint. A **mismatch** (or the
  habit failing to execute at all, e.g. a tool returned a shape that breaks a later step) is reported as
  **divergence** — the run's output is not trusted. (Steps whose output shape legitimately varies have no
  fixed fingerprint and are skipped, so we don't false-alarm on them.)
- **Fallback loop** (`run_task`): route → run the monitored habit; if it did **not** diverge, return the
  habit's output (mode `"habit"`); if it **diverged**, run the live agent and return that (mode
  `"fallback"`); if no habit applied, run the live agent (mode `"live"`). So a caught anomaly simply
  falls back to the slow, safe path — we're never stuck with a wrong answer.
- **Recompile-on-drift** (`DriftMonitor`): watches recent run modes; when the recent **fallback rate**
  exceeds a threshold, the habit is stale (the world changed) and we recompile from fresh trajectories —
  which the live agent recorded while handling the new world — producing a new habit that runs the
  changed world cleanly again.

---

## 8. End-to-end, in one paragraph

A task arrives. The **router** checks for a usable habit. If one applies, the **habit interpreter**
runs the recipe with **no LLM calls**, the **context policy** keeps only what each step needs, and the
**divergence detector** watches every tool result's shape. If everything looks normal, we return the
answer in sub-milliseconds. If a result's shape is off — or no habit applies — we **fall back** to the
full LLM agent, and the **recorder** logs that run (every step, its tokens, its timing, what it read,
and — via the pure-code **checker** — whether it was correct) into the **store**. Offline, the
**compiler** clusters those correct runs, induces the recipe and its provenance, **replay-validates** a
new habit, and the **context layer** induces and **safety-validates** its memory policy. If habits keep
failing (drift), we **recompile**. Cost and latency are read straight off the records (LLM-call count,
token usage per LLM step, wall-clock per task) — which is how we show the habit reproduces the agent's
correct answers at **zero calls, zero tokens, sub-millisecond latency** on repeat work.
