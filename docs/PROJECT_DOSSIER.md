# HABIT — Project Dossier (full context for the paper)

*Everything implemented, every research finding, every design decision, and where we're going.
Written as the backbone for the research paper and for full team context. Last updated: 2026-08-31.*

---

## 0. One-paragraph summary

HABIT is a self-optimizing runtime for LLM agents. It records agent runs as structured
**trajectories**, **clusters** the recurring ones, **compiles** each recurring recipe into a
deterministic, LLM-free **habit** (validated by held-out replay before it is trusted), induces
**per-step context policies** from the observed access patterns (what each step actually reads), and
at runtime routes tasks to habits while detecting mid-run divergence and falling back to the live
agent. Tagline: *muscle memory for AI agents — decide once, execute forever.*

---

## 1. Where we are right now (2026-09-01)

- **ALL FOUR LAYERS ARE COMPLETE and verified.** Recorder (L1), Compiler (L2), Context (L3), and the
  full Runtime loop (L4) are built, tested, and green (~185 tests, mypy strict, ruff clean). The whole
  HABIT thesis — observe → compile → route → detect divergence → fall back → recompile on drift — is
  implemented and demonstrated end to end.
- **Headline results achieved (offline):** (a) a compiled habit reproduces the agent's correct output
  on **unseen** tasks with **0 LLM calls / 0 tokens** at 1.000 success across three domains; (b) the
  learned context policy shrinks the window 20–50% on the real domains and survives a long-horizon
  task (naive dies at n items, HABIT stays at 2, 90–98% savings) with a proven no-starvation gate;
  (c) the online loop routes to habits, catches injected anomalies (100% shape-anomaly catch, 0%
  false aborts), falls back safely, and recompiles to resolve drift.
- **What remains is DELIVERY, not new mechanism:** a real Groq/Ollama cost pass (harness ready), the
  baseline ladder (semantic-cache / AWM-text / Compiled-AI-style / PreAct-style), benchmark freeze +
  Pareto, the split-screen demo, a second framework adapter (descope candidate), and the paper/report.

Direction of travel: **real-model cost pass → baseline ladder → benchmark freeze → demo → paper.**

---

## 2. The problem (paper: Introduction / Motivation)

LLM agents have no memory of their own past work: they solve every task from zero, calling a costly
model at *every* step — even for work they have already done correctly thousands of times. This
causes three coupled failures:
- **Cost:** every step is a paid model call; at enterprise volume this is the #1 deployment blocker.
- **Reliability:** each step is probabilistic (~85%), so long tasks fail often (0.85^10 ≈ 20%); there
  is no way to make routine steps deterministic.
- **Context overflow:** the finite context window fills with everything, so long tasks "forget."

Root cause (the thesis): **agents re-derive at runtime the knowledge already latent in their own run
history**, and nothing in today's stack learns from it.

---

## 3. What we have implemented (paper: System / Method)

The system is four layers. Status: **L1 done, L2 done, L3 starting, L4 not started.**

### Layer 1 — Recorder (DONE)
- **Trajectory schema** (`habit.schemas`, Pydantic v2, frozen): `Trajectory`, `Step`, `LLMCall`,
  `ToolCall`, `ContextItem`, `Outcome`; enums `StepType`, `ContextKind`. Enforces step-payload
  invariants, a **tool-result structure fingerprint** per step (`tool_result_schema_fingerprint`),
  per-step **context-access records** (`context_available` / `context_reads`), timezone-aware
  timestamps, and referential integrity. Aligned to OpenTelemetry GenAI field names. Round-trips
  losslessly through JSON.
- **`schema_fingerprint`** — deterministic, value-independent hash of a tool result's key/type
  structure (stable across values/key-order/length). The signal Layer 4's divergence detector will
  use.
- **Storage** (`habit.storage`) — SQLAlchemy 2.x `TrajectoryStore`; backend chosen only by
  `DATABASE_URL` (SQLite default, Postgres by changing one variable). Lossless JSON payload + indexed
  `domain`/`success`/`started_at`.
- **Recorder** (`habit.recorder`) — framework-agnostic; assembles steps into a validated trajectory,
  auto-numbers steps, normalizes UTC, computes fingerprints internally.
- **LangGraph adapter** (`habit.adapters`) — records a real LangGraph/LangChain run via callbacks
  (proves the framework-agnostic claim).

### Layer 2 — Compiler (DONE) — the recipe → habit pipeline
- **Clustering** (`habit.compiler.clustering`) — groups trajectories by exact **structural
  signature** (ordered `(step_type, tool_name)`). Recovers the 3 domains at purity 1.0. (Fuzzy
  embedding/HDBSCAN clustering is a deferred upgrade for when trajectories branch.)
- **Skeleton induction** (`habit.compiler.skeleton`) — per-step **stability analysis**: a step is
  `stable` iff it is a deterministic tool step whose reads and result-shape are identical across the
  cluster. *(Finding: report's `aggregate` step is legitimately non-stable — its output dict has
  variable keys, so its structure fingerprint varies. This distinguishes "compilable" from
  "shape-stable/checkable-by-fingerprint" — important for the divergence detector.)*
- **Crystallizer** (`habit.compiler.crystallizer`) — **automatically induces provenance** by
  value-matching: for each tool argument and each output field, it finds a consistent source across
  the cluster (priority: input-field > whole-input > prior-result-field > whole-result > constant).
  Produces a `HabitPlan` executed by a **pure interpreter (`run_habit`) — no LLM, no `exec`**.
- **Replay-validation gate** (`habit.compiler.validation`) — `compile_habit` splits a cluster into
  train/held-out, crystallizes on train, and validates on held-out; a `CompiledHabit` is `usable`
  **iff** it reproduced the correct output on every held-out run. Enforces the hard rule that an
  unvalidated habit is never usable. A deliberately broken plan is correctly rejected.

### Layer 3 — Context policies (STARTING, T23) — the headline novelty
- Induce, from the corpus's faithful `context_reads`, a **per-step context manifest** (what each step
  needs) and a **liveness-based eviction policy** (keep items read now-or-later; evict items never
  read again). Next: paging/prefetch execution (T24), a correctness validator that proves the policy
  never starves a step (T25), and the long-horizon "naive overflows / HABIT survives" study with
  token-savings numbers (T26).

### Layer 4 — Runtime + safety net (NOT STARTED)
- Router (match a task to a usable habit), **divergence detector** (per-step fingerprint/value
  checks), safe fallback to the live agent, and recompile-on-drift. Planned T18–T22, with the
  detector reported as an ROC (missed-divergence vs. false-abort).

### Supporting
- **Workloads** (`habit.workloads`) — three DocILE-aligned/pure-code-checked domains (invoice,
  ticket, report) + an arithmetic example, each with parameterized generators, mock tools, a
  pure-code ground-truth checker, and a held-out distribution-shifted split.
- **Baseline agents** (`habit.baseline`) — authored per-domain workflows that record **faithful
  per-step context reads** (the Layer-3 data) via a shared `BaselineTrace`; offline `FakeModel`.
- **Eval** (`habit.eval`) — corpus generator (1000+/domain) and the live-vs-habit benchmark.

---

## 4. Empirical results so far (paper: Experiments)

**Corpus:** 3,000+ trajectories (1000/domain) with faithful per-step context reads; baseline success
1.000 (the baseline uses correct deterministic tools).

**Headline benchmark (live agent vs. compiled habit, on FRESH unseen tasks):**

| Domain | System | Success | LLM calls/task | Tokens/task |
|---|---|---|---|---|
| invoice | live | 1.000 | 5 | 50 (FakeModel) |
| invoice | **habit** | **1.000** | **0** | **0** |
| ticket | live | 1.000 | 6 | 60 (FakeModel) |
| ticket | **habit** | **1.000** | **0** | **0** |
| report | live | 1.000 | 6 | 60 (FakeModel) |
| report | **habit** | **1.000** | **0** | **0** |

**Reading:** the compiled habit matches the agent's success on unseen tasks while eliminating **100%
of LLM calls**. Latency with FakeModel is ~150–300× lower (structural, not a real-model number).
Independent generalization check: habits compiled on `seed=0` scored **150/150** on `seed=99` tasks.

**Real-model cost (Groq, gpt-oss-20b — done, not synthetic):** on real infrastructure the live agent
vs. the compiled habit:
- invoice — live: 5 calls, ~1,843 tokens, **4.3 s/task**; habit: **0 calls, 0 tokens, ~0.03 ms**.
- ticket — live: 6 calls, ~1,589 tokens, **6.0 s/task**; habit: 0 / 0 / ~0.04 ms.
- report — live: 6 calls, ~2,642 tokens, **17.9 s/task**; habit: 0 / 0 / ~0.04 ms.
Both at 1.000 success. The habit eliminates **100% of API calls, ~1.6–2.6k tokens/task, and 4–18 s
of latency** — a ~10⁵× latency reduction on repeat tasks, with real inference tokens (not FakeModel).
(Model note: the account lacked llama-3.3-70b-versatile, so the run used gpt-oss-20b via --groq-model;
the harness is model-agnostic. A local Ollama model would allow larger free/faster runs.)

**Layer-3 results (context policies — the headline novelty):**
- **Working-set reduction on the 3 real domains** (liveness eviction): peak context window shrinks
  invoice 5→4 (20%), ticket 8→5 (38%), report 6→3 (50%).
- **Long-horizon survival study** (a controlled chain where old context goes dead): the naive
  keep-everything window grows to n items and overflows a budget ("dies"); HABIT's learned policy
  stays bounded at **2 items** and stays under budget ("survives"). Token savings **90% / 96% / 98%**
  at n = 20 / 50 / 100.
- **Safety gate:** the induced policy is proven to never starve a held-out run (zero starvations) —
  the Layer-3 analog of the Layer-2 replay-validation gate. Effective *and* provably safe.

**Layer-4 results (the online runtime loop + safety net):**
- **Closed loop, three modes:** route → run the monitored habit; on a clean run serve the habit
  output ("habit"), on divergence fall back to the live agent ("fallback"), and when no habit applies
  run the live agent ("live") — all three demonstrated producing correct output.
- **Divergence detector operating point (adversarial injection):** the structure-fingerprint detector
  catches **100% of schema/shape anomalies with 0% false aborts**, and — by construction — **0% of
  value-only anomalies** (same shape, changed value). That measured blind spot is the explicit
  motivation for the value-range / learned v2 detector (T27). *(v1 is threshold-free, so this is an
  operating point per anomaly type; a swept ROC comes with v2.)*
- **Recompile-on-drift:** a `DriftMonitor` flags a stale habit when the recent fallback rate exceeds a
  threshold; recompiling from fresh new-world trajectories restores clean, divergence-free habit
  execution — the self-optimizing loop closed.

---

## 5. Research findings & novelty (paper: Related Work + Contributions)

### Base paper and closest prior work
- **Base paper: Agent Workflow Memory (AWM), ICML 2025** (peer-reviewed). Induces reusable workflows
  from an agent's own runs — but stores them as **natural-language text re-read by the LLM every
  step** (improves accuracy, not cost/determinism; no safety net; no memory management).
- **Closest contemporary (2026 preprints), differentiate from these:**
  - **PreAct** (Bojie Li, arXiv 2606.17929): compiles a successful run into a replayable state
    machine with per-step checks + fallback + a store-time verification gate — but for **GUI/screen
    agents**, from a **single run**, with **no memory layer**.
  - **Compiled AI** (arXiv 2604.05150): compiles to deterministic code with a 4-stage validation gate
    and reports 57× token / 450× latency on invoices — but **from a human-written spec**, with **no
    online loop and no context layer**.
  - **Skill-DisCo** (2606.26669): traces → executable verifiable skills (FSM subgraphs), offline.

### HABIT's novelty map (which claims are strong)
1. **Trajectory-induced per-step context policies (compiler→memory link)** — **STRONGLY NOVEL.** No
   surveyed system induces what each step needs from cross-trajectory access patterns and hands it to
   a deterministic paging layer. **This is the headline (Layer 3).**
2. **Public cost–reliability benchmark** across compilation aggressiveness — **moderately novel** as
   an open, reusable artifact.
3. **Online runtime loop** (observe→compile→route→recompile) — **weakly novel** (PreAct did it for
   GUI agents); we frame it as a port to structured **tool-call** agents with **cross-trajectory
   clustered** skeletons.
4. **Divergence detection + fallback** — **weakly novel**; our slice is divergence over structured
   tool-I/O fingerprints (not screens), reported as an ROC.

### Our own findings so far (worth writing up)
- **Automatic provenance induction by value-matching generalizes**: habits compiled from a handful of
  runs reproduce correct outputs on unseen tasks (150/150) with zero model calls — evidence that the
  induced recipe captures the true dataflow, not memorized values.
- **Structure-fingerprint stability is a real, useful signal — with a caveat**: steps whose output
  *schema* depends on the input data (e.g. an aggregate whose keys vary) are legitimately not
  shape-stable, so a fixed fingerprint can't be their divergence signal. The skeleton's stability
  analysis surfaces exactly these steps — informs a smarter Layer-4 detector.
- **Liveness gives a principled eviction policy** (Layer 3, in progress): items are kept only while
  read now-or-later; e.g. the raw invoice becomes evictable after the last step that reads it — a
  clean, learned analog of register/GC liveness for context windows.

### Metrics/methods we plan to adopt (borrowed, defensible)
- **pass^k** (τ-bench) as the primary reliability metric (replaces the illustrative 0.85^10 math).
- **Compiled AI's** metric suite (token-amortization break-even, determinism-as-entropy, TCO).
- **PreAct's** with-gate/without-gate ablation framing for our replay-validation gate.
- **Divergence detector as an ROC** (missed-divergence vs. false-abort).
- **AWM's** generalization-gap evaluation (widen train/test distribution — we already have shifted
  splits ready).

---

## 6. Key design decisions (paper: Method rationale / Appendix)

- **Trajectory schema frozen from day one** with the fingerprint + context-read fields — because they
  cannot be backfilled and every layer depends on them.
- **Baseline records context reads explicitly** (authored workflows), not via callbacks/heuristics —
  chosen so Layer-3 data is faithful; mock tools produce correct results, LLM steps represent cost.
- **Provenance induced automatically** (value-matching), not hand-specified — the stronger "compile
  from data" story; replay-validation is the safety net against a bad induction.
- **Habit = compiled plan + pure interpreter (no LLM, no `exec`)** — fully deterministic and offline;
  emitting literal Python source is an optional later step.
- **Structural-signature clustering (deterministic) first**; embedding/HDBSCAN deferred until
  trajectories branch.
- **Real Groq model deferred to a later cost pass** — the corpus and benchmark are model-pluggable;
  FakeModel keeps everything offline and reproducible.

---

## 7. Reviewer attack list (be ready to answer)

- *"PreAct already did compile→replay→check→fallback."* → Different agent class (tool-call vs GUI),
  **clustered general** skeleton (not per-run macro), and a **context layer PreAct lacks**.
- *"Compiled AI already hit 57× on invoices."* → They compile from a **hand-written spec**; we
  **induce from logs**, and add the online loop + context layer they lack.
- *"Isn't Layer 3 just MemGPT?"* → MemGPT lets the **LLM decide paging at runtime** (costly,
  reactive); ours is a **deterministic, LLM-free policy learned from what each step actually read**,
  applied predictively.
- *"Synthetic workloads = rigged."* → Pure-code checkers (no LLM judge), DocILE-aligned invoices,
  held-out distribution-shifted splits; a real-model pass planned.
- *"How is divergence real vs. a false abort?"* → Reported as an ROC (planned T21), citing the
  reliability-science framework.
- *"Base paper is a preprint."* → Formal base paper is **AWM (ICML 2025, peer-reviewed)**; PreAct is
  cited as the closest contemporary work we differentiate from.

---

## 8. Paper scaffold (how this maps to a submission)

- **Contributions:** (1) trajectory-induced per-step **context policies** linking the compiler to
  memory (headline); (2) an **online compile→validate→route→fallback** runtime for tool-call agents;
  (3) an open **cost–reliability benchmark** across three domains with generators + baselines.
- **Method:** the four layers (§3).
- **Experiments:** headline cost/success table (have it); Layer-3 token-savings + long-horizon
  survival (T26); divergence ROC + drift-cost (T21–T22); baseline ladder (vanilla / semantic-cache /
  AWM-text / Compiled-AI-style / PreAct-style / HABIT).
- **Related work:** §5.
- **Target venue:** an agents/LLM-systems workshop or demo track; IEEE ICA (Agentic AI) is a possible
  home. Keep references peer-reviewed where possible (AWM, AFlow, ADAS, DSPy, Voyager, MemGPT + the
  IEEE/Springer agent surveys).

---

## 9. What is NOT done / risks (be honest)

- **Real-model cost/latency numbers** — need one Groq/Ollama pass (harness is ready).
- **Layer 3 beyond induction** — paging/prefetch, correctness validator, long-horizon study (T24–T26).
- **Layer 4 entirely** — router, divergence detector, fallback, recompile-on-drift (T18–T22).
- **Branching / noisy recipes** — the compiler is proven on clean single-recipe domains; fuzzy
  clustering + variable-step handling is the harder generalization.
- **Second framework adapter, dashboard/demo, benchmark freeze, paper** — later phases.

---

## 10. Where we're moving (roadmap)

1. **Layer 3 (headline):** induce context manifests (T23, now) → paging/prefetch (T24) → policy
   correctness validator (T25) → long-horizon token-savings/survival study (T26).
2. **Layer 4 (runtime + safety net):** router (T18) → divergence v1 (T19) → fallback (T20) →
   adversarial-injection ROC (T21) → recompile-on-drift + drift-cost (T22) → divergence v2/XGBoost (T27).
3. **Evaluation:** real-model cost pass; baseline ladder (T28); benchmark freeze + Pareto (T29).
4. **Delivery:** split-screen demo (T30); second adapter (T31, descope candidate); paper + report (T32).

**Bottom line:** the core thesis is working and verified on three domains; the genuinely novel part
(Layer 3) is next with the right data already in hand. The two things that most raise the ceiling: a
strong Layer-3 result and one real-model cost run.
