# HABIT vs. Prior Work — What We Are Doing Differently

*A plain-language + technical explainer for teammates, evaluators, and reviewers.*
*Last updated: 2026-07-20. Maintained by Member 1 (architecture/research).*

---

## 1. HABIT in one paragraph

Today's LLM agents are stuck on "day one" forever: an agent processes its 10,000th invoice
exactly like its 1st — calling a large language model at every step, paying full cost and full
latency every time, even though the task is identical to thousands it has already done. **HABIT is
a self-optimizing runtime that gives agents muscle memory.** It records agent runs as structured
*trajectories*, compiles the repeated parts into cheap deterministic code ("habits"), learns *what
information each step actually needs* and pages the rest out of the context window, and at runtime
routes tasks to habits — while watching for anything going off-script and instantly handing control
back to the full LLM agent when it does. Decide once, execute forever.

**Framings that help people "get it":**
- *System 1 / System 2 for agents.* Habits are System 1 (fast, cheap, automatic). The live LLM is
  System 2 (slow, expensive, deliberate). HABIT decides which one should drive at each moment.
- *A JIT compiler + virtual memory for agents.* Hot paths get compiled to deterministic code; cold
  (novel) paths stay interpreted by the live LLM; context is paged in and out like OS memory.

The four layers:
1. **Recorder (Layer 1)** — logs every run as a validated trajectory.
2. **Compiler (Layer 2)** — clusters similar runs, extracts the stable skeleton, generates
   deterministic code, and replay-validates it before trusting it.
3. **Context (Layer 3)** — learns per-step context policies from observed access patterns
   (what each step read) and pages/prefetches accordingly. **← our headline contribution.**
4. **Runtime (Layer 4)** — routes tasks to habits or the live agent, detects mid-run divergence,
   falls back safely, and recompiles when the world drifts.

---

## 2. The competitive landscape at a glance

| Prior work | What it does | What HABIT does differently |
|---|---|---|
| **PreAct** (2606.17929) | Compiles a successful **GUI** run into a replayable state machine; per-step screen-checks; hands back to the agent on mismatch; stores only if a verifier confirms success. | Works on **structured tool-call/API agents** (not screens); compiles a **cross-trajectory-clustered general skeleton** (not a per-run macro); adds a **context/memory layer** PreAct has none of. |
| **Compiled AI** (2604.05150) | LLM compiles a **human-written YAML spec** into deterministic code; 4-stage validation gate; 57× token / 450× latency on invoices. | Induces the workflow **from observed logs** (no hand-written spec); adds an **online divergence/fallback loop** and **context policies** it lacks. |
| **Agent Workflow Memory (AWM)** (2409.07429) | Induces reusable workflows from trajectories, stored as **natural-language text** re-read by the LLM each time. | Compiles to **executable code** (zero-LLM hot path) → real cost/determinism gains, not just accuracy. Adds divergence detection + context. |
| **Skill-DisCo** (2606.26669) | Distills traces into **executable, verifiable procedural skills** (FSM subgraphs), offline. | Runs as an **online runtime** (route live traffic, detect divergence, fall back, recompile) and induces **context policies** — neither is in Skill-DisCo. |
| **Trace2Skill** (2603.25158) | Consolidates trajectories into **textual skill guides**. | Executable code, not text; plus runtime loop + context layer. |
| **AFlow / ADAS** (2410.10762 / 2408.08435) | Automatically **design/optimize agent workflows** — but every node stays an LLM call. | We **remove** LLM calls on hot paths (determinism + cost), and run live with a safety net; they're design-time optimizers. |
| **Voyager** (2305.16291) | Builds a **skill library of executable code** to explore Minecraft; verifies before storing. | Goal is **efficiency + reliability on repeated tasks**, not open-ended exploration; adds divergence/fallback for compiled skills serving live traffic, plus context policies. |
| **MemGPT / Letta** (2310.08560) | **LLM decides** at runtime what to page in/out of context (virtual memory). | Our paging policy is **learned offline from usage** and applied **deterministically** (LLM-free) with **prefetching** — cheaper and predictive, not reactive. |
| **Mem0 / Zep** | Conversational **fact memory** retrieved by similarity. | We do **procedural + per-step working-set** memory driven by tool-access patterns — a different memory type and trigger. |
| **DSPy** (2310.03714) | "Compiles" **prompts** (optimizes wording/demos). | We compile **whole workflows to code**; we *use* DSPy as tooling for the few residual small-model calls. |
| **Semantic caching** (GPTCache, vCache) | Reuse a cached **single response** if the new query is similar. | We reuse a **verified multi-step procedure** with per-step divergence checks and outcome validation — cache reuse *with a safety net*. |

---

## 3. The base paper: PreAct — side by side

We take **PreAct: Computer-Using Agents that Get Faster on Repeated Tasks**
([arXiv 2606.17929](https://arxiv.org/abs/2606.17929), June 2026) as our base paper, because it is
the closest structural match to HABIT's runtime loop. Extending and differentiating from it *is*
our contribution.

| Dimension | PreAct | HABIT |
|---|---|---|
| **Agent type** | Computer-using (GUI) agents — clicks/typing on a screen | Structured **tool-call / API** agents (function calls with typed I/O) |
| **What gets compiled** | One **successful run** → a state-machine macro | **Many clustered trajectories** → a **general parameterized skeleton** |
| **Divergence signal** | Does the **screen** match what the program expects? | Does the **tool-result structure** (schema/type fingerprint) and value range match? |
| **Fallback** | Hand control back to the agent on mismatch | Same idea — pause habit, re-inflate context, resume live agent |
| **Store-time gate** | Program stored only if an independent evaluator confirms it solved the task | Same idea — replay-validation gate before a habit goes live |
| **Context/memory** | **None** | **Layer 3: per-step context policies induced from trajectories** ← unique |
| **Openness** | Research prototype, GUI-domain | Open-source, framework-agnostic, tool-call domains + public benchmark |

**One-paragraph positioning statement (use this verbatim in the report/synopsis):**

> We take **PreAct** as our base paper — it shows that a successful agent run can be compiled into a
> replayable program guarded by mid-run checks and a store-time verification gate. HABIT extends this
> from **GUI agents to structured tool-call agents**, generalizes **per-run macros into
> cross-trajectory-clustered skeletons**, and adds a capability absent from all prior work:
> **context policies induced from the same trajectories**, so the compiler tells the memory system
> exactly what each step needs.

*(Fallback option if an evaluator wants a more established base paper: use **AWM**, ICML 2025, as the
foundational anchor and treat PreAct + Compiled AI as the closest contemporary work we differentiate
from.)*

---

## 4. The second-closest paper: Compiled AI — why we're still different

**Compiled AI** ([arXiv 2604.05150](https://arxiv.org/abs/2604.05150), Apr 2026) is our Layer-2 twin:
it compiles workflows to deterministic code, uses a four-stage validation gate
(security → syntax → execution → accuracy), and reports the exact metrics we care about
(57× token reduction, break-even ≈ 17 transactions, determinism-as-zero-entropy) — and it does this
on **invoices**, which is our Domain 1.

**So what's left for us?**
- Compiled AI compiles **from a human-written YAML spec**. HABIT **induces the workflow from observed
  logs** — no human specification. (We can even measure: how well does induction recover the spec?)
- Compiled AI has **no online loop** — no live routing, no mid-run divergence detection, no graceful
  fallback. HABIT's runtime safety net is exactly what they lack.
- Compiled AI has **no context/memory layer**. HABIT's Layer 3 is entirely outside their scope.
- Their own paper reports a telling failure mode: **4% of compiled artifacts are syntactically valid
  but semantically wrong.** That is *precisely why a divergence detector is necessary* — we cite this
  as motivation.

**What we deliberately borrow from them** (so our numbers are comparable and defensible): their metric
suite (token-amortization break-even, determinism-as-entropy, total-cost-of-ownership) and their
four-stage validation gate, which we adopt as our replay-validation spec.

---

## 5. The novelty map — how strong is each HABIT claim?

| HABIT claim | Verdict | Why |
|---|---|---|
| **Trajectory-induced context policies** (Layer 3 — the compiler tells memory what each step needs) | **STRONGLY NOVEL** | No surveyed system induces per-step context manifests from cross-trajectory access patterns and hands them to a deterministic, LLM-free paging layer. MemGPT lets the LLM decide; Mem0/Zep do conversational facts; eviction papers use generic heuristics. **This is our headline.** |
| **Public cost–reliability benchmark** (HABIT-Bench) | **MODERATELY NOVEL** | Compiled AI has the metrics on invoices; τ-bench has reliability. Novel as a **reusable, open artifact spanning the compilation-aggressiveness Pareto frontier across 3 domains with open generators.** |
| **Online runtime loop** (observe → compile → route → recompile-on-drift) | **WEAKLY NOVEL** | PreAct published this loop for GUI agents in June 2026. Survives as "the same loop for **tool-call** agents with **clustered** skeletons." Frame as an engineering port, not a first-of-kind. |
| **Divergence detection + fallback** | **WEAKLY NOVEL** | PreAct does per-step checks + hand-back + a verification gate. Our slice: divergence over **structured tool-I/O schemas + value distributions** (not screens), reported as an ROC (miss-rate vs. false-abort). Don't claim first-of-kind. |

**Bottom line:** lead every explanation with **Layer 3 (learned context policies)**. That is the part
nobody else has built. The runtime loop is solid engineering, but it is no longer unprecedented.

---

## 6. "If someone asks…" — quick, honest answers

- **"PreAct already did the compile-and-replay loop. What's new?"** → Different agent class
  (tool-call vs. GUI), a *clustered general* skeleton vs. a per-run macro, and a context layer PreAct
  has none of. We benchmark directly against a PreAct-style baseline.
- **"Compiled AI already hit 57× on invoices. What's new?"** → They compile from a hand-written spec;
  we induce from logs. They have no online divergence/fallback and no context layer. We adopt their
  metrics so the comparison is fair.
- **"Isn't Layer 3 just MemGPT?"** → MemGPT lets the LLM decide paging at runtime (costly, reactive).
  Ours is a deterministic, LLM-free policy **learned from what each step actually read**, applied
  predictively (prefetch). Different source, different cost.
- **"Your workloads are synthetic — did you rig the result?"** → Synthetic gives objective,
  code-based ground-truth checkers (no LLM judge) and controllable drift. We anchor Domain 1 to the
  public **DocILE** invoice distribution and use held-out, distribution-shifted test splits.
- **"How do you know a fired divergence was real?"** → We report the detector as an **ROC curve**
  (missed-divergence vs. false-abort), not a single accuracy number, and pick an operating point per
  cost tolerance.
- **"When the API changes, your habit is stale — is maintenance worth it?"** → Drift triggers
  recompile-from-fresh-trajectories; if drift is faster than the ~17-run break-even, the router
  correctly routes to the live agent instead. We measure net cost including recompiles.

---

## 7. What is uniquely ours (the one-line summary)

> Everyone else either **stores reusable behavior** (AWM, Trace2Skill, Skill-DisCo, Voyager),
> **optimizes workflows** (AFlow, ADAS, DSPy), **compiles from a spec** (Compiled AI),
> **replays GUI macros** (PreAct), or **manages memory generically** (MemGPT, Mem0, Zep).
> **HABIT is the first to close the loop as a live runtime for tool-call agents *and* to induce, from
> the same trajectories, the per-step context policies that tell the memory system what each step
> needs** — linking compilation to context management, which appears in no prior paper.

---

## 8. Sources

PreAct [2606.17929] · Compiled AI [2604.05150] · AWM [2409.07429] · Skill-DisCo [2606.26669] ·
Trace2Skill [2603.25158] · AFlow [2410.10762] · ADAS [2408.08435] · Voyager [2305.16291] ·
MemGPT/Letta [2310.08560] · DSPy [2310.03714] · Beyond Compaction [2606.11213] ·
Slipstream [2605.08580] · Beyond pass@1 (reliability) [2603.29231] · Why Agent Caching Fails [2602.18922].
