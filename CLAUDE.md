# HABIT — Project Instructions

HABIT is a self-optimizing runtime for LLM agents. It records agent runs as trajectories, compiles repeated behavior into deterministic code ("habits"), induces per-step context policies from observed access patterns, and at runtime routes tasks to habits while detecting mid-run divergence and falling back to the live LLM agent.

Tagline: *Muscle memory for AI agents — decide once, execute forever.*

## Architecture

Four layers. Never blur their boundaries.

- **Layer 1 — Recorder** (`src/habit/recorder/`): wraps an agent framework, emits validated `Trajectory` objects, persists them.
- **Layer 2 — Compiler** (`src/habit/compiler/`): clusters trajectories, induces stable skeletons, generates deterministic habits, replay-validates them before they are trusted.
- **Layer 3 — Context** (`src/habit/context/`): induces per-step context policies from access patterns; paging and prefetch.
- **Layer 4 — Runtime** (`src/habit/runtime/`): routes tasks to habits or the live agent, detects divergence mid-run, falls back safely, triggers recompilation on drift.

Supporting: `src/habit/schemas/` (data contracts), `src/habit/interfaces.py` (layer protocols), `src/habit/adapters/` (framework integrations), `src/habit/workloads/` (synthetic task generators), `src/habit/eval/` (metrics and benchmark).

## Code standard

Write the code a senior engineer would ship. Not a tutorial, not a demo.

- **Minimal.** Solve exactly the stated problem. No speculative generality.
- **No unnecessary abstraction.** No wrapper functions with one caller. No factories, no base classes with a single subclass, no config layers we don't need yet.
- **No defensive bloat.** No try/except that only re-raises. Do not re-validate what Pydantic already validates. No error handling for cases that cannot occur.
- **Comments: heading only.** One short comment per module or per logical section stating what that part does. No line-by-line commentary, no docstrings restating the signature, no noise. If code needs explaining, rename things instead.
- **Full type hints.** Everywhere, including return types.
- **Explicit over clever.** Boring, debuggable code wins.
- **Fail loudly and early.** Raise clear exceptions with useful messages. Never silently default.
- **No dead weight.** No TODOs, no placeholder code, no unused imports, no `if __name__ == "__main__"` example blocks in library modules.
- **Short, single-purpose functions. Focused files.**
- Explanations belong in the Handoff Report, never in the code.

## Hard rules

- **The trajectory schema is frozen.** Never modify `src/habit/schemas/trajectory.py` without explicit approval. Every layer depends on it. If a field seems missing, stop and flag it — do not add it unilaterally.
- **Conform to `interfaces.py`.** If existing code violates a protocol, refactor that code to conform. Never add shims or adapters to work around it.
- **Tests run offline.** Every test must pass with no API key and no network. Use scripted fake LLMs and mock tools.
- **No LLM calls in library code paths that claim to be deterministic.** Habits call small models only at explicitly variable steps.
- **A habit that has not passed replay validation is never marked usable.**
- **Ground-truth checkers are pure code.** Never use an LLM to judge task success.
- **One task per session.** Do not build ahead into work that belongs to a later task.

## Storage

Storage goes through the `TrajectoryStore` protocol, backed by SQLAlchemy. Default is SQLite via `DATABASE_URL=sqlite:///habit.db`; PostgreSQL is supported by setting `DATABASE_URL=postgresql+psycopg://...` with no code change. Use JSON columns for step payloads; index `domain`, `outcome`, and `started_at`. Never write raw SQL that only works on one backend.

## Stack

Python 3.11+ · Pydantic v2 · SQLAlchemy 2.x · LangGraph · Groq (large model) · Ollama (small model) · sentence-transformers · scikit-learn · DSPy · XGBoost · tiktoken · FastAPI · React + Recharts (dashboard only) · pytest · ruff

## Commands

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
ruff format src tests
```

## Conventions

- `src/` layout, package name `habit`.
- Conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- Every design decision not specified by the task goes in `docs/decisions.md` as a dated entry.
- Never commit. The human commits manually after review.

## Handoff Report

End every task with this block, complete, no sections skipped:

```
1. TASK ID + one-line summary.
2. FILES CREATED/MODIFIED: full paths, one-line purpose each.
3. KEY CODE: the most important 30-60 lines.
4. DESIGN DECISIONS MADE: anything chosen without instruction, and why.
5. TESTS: what exists, exact command, actual pass/fail output.
6. HOW TO VERIFY MANUALLY: exact commands.
7. DEVIATIONS FROM THE PROMPT: or "None".
8. ASSUMPTIONS + OPEN QUESTIONS.
9. WHAT IS NOT DONE.
```
