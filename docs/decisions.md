# Design Decisions

## 2026-07-19 — Project skeleton (T1)

- **Build backend: hatchling.** The task allowed hatchling or setuptools. Hatchling is
  the modern default and lets the src layout be declared explicitly via
  `[tool.hatch.build.targets.wheel] packages = ["src/habit"]`.
- **Ruff rule config lives under `[tool.ruff.lint]`.** Recent ruff versions moved the
  `select` key into the `lint` subtable; `target-version` stays under `[tool.ruff]`.
- **Ruff/mypy config in pyproject.toml, not separate files.** Fewer top-level files;
  both tools read pyproject natively.
- **`mypy` invoked with no arguments** in CI and locally, relying on
  `files = ["src", "tests"]` in config, matching the task's `mypy` step.

## 2026-07-19 — Trajectory schema (T2)

- **Schema module path is `src/habit/schema.py`** as the task specified, not the
  `src/habit/schemas/trajectory.py` path named in CLAUDE.md. Flagged as an open question for
  Member 1; implemented the task path verbatim.
- **`context_reads ⊆ context_available` enforced on `Step`**, while cross-item referential
  integrity (item_ids exist in `context_items`) is enforced on `Trajectory` — the subset
  check needs only step-local data, the existence check needs the registry.
- **`size_tokens` given `default=None`** so `ContextItem` can omit it; all other nullable
  fields are required-explicit per the spec's shape.
- **Fingerprint `default` NOT applied elsewhere** — every other field is explicit to force
  the recorder (T5) to populate deliberately.

## 2026-07-19 — Schema relocation to canonical path (T2b)

- **Moved `src/habit/schema.py` → `src/habit/schemas/trajectory.py` and
  `src/habit/fingerprint.py` → `src/habit/schemas/fingerprint.py`**, byte-identical, to match
  the frozen data-contract location in CLAUDE.md. `src/habit/schemas/__init__.py` re-exports the
  public API so callers do `from habit.schemas import ...`. No shims left at the old flat paths.
  Resolves the T2 path open-question.

## 2026-07-19 — Persistence backend (T4)

- **SQLAlchemy 2.x ORM backend.** Implemented `SqlAlchemyTrajectoryStore` implementing the
  `TrajectoryStore` protocol. Backend selection is purely driven by `DATABASE_URL` environment
  variable, defaulting to `sqlite:///habit.db`.
- **Hybrid relational/JSON storage.** Indexed scalar columns (`trajectory_id`, `domain`,
  `task_type`, `success`, `started_at`) enable efficient filtering and ordering, while the
  full JSON payload preserves 100% losslessness of `Trajectory` fields and timezone awareness.
- **Reconstruction strictly from JSON payload.** `get()` and `query()` validate directly from
  `row.payload` (`Trajectory.model_validate(row.payload)`) rather than scalar ORM fields.
- **PostgreSQL driver dependency optional.** Added `sqlalchemy>=2` to `dependencies` in
  `pyproject.toml`. `psycopg` is omitted from mandatory dependencies to maintain a lightweight,
  zero-setup SQLite default; production PostgreSQL deployments install `psycopg` separately.

## Decisions

- 2026-10-12 (T-REL): `UnreliableModel` is a plain class holding a `random.Random`, not a frozen dataclass — it carries per-call RNG state, which a frozen dataclass cannot mutate.
- 2026-10-12 (T-REL): typed `reliability_study`'s `workload` param with the existing local `ShiftableWorkload` Protocol (from `research.py`), not the frozen `WorkloadGenerator` — keeps the eval package consistent and mypy-strict clean without touching the frozen base Protocol.
- 2026-10-12 (T-REL): `live_success_rate` requires both run completion AND `ground_truth_match is True` — a completed-but-wrong run is not a success, so the measured curve reflects true end-to-end reliability.
- 2026-10-12 (T-REL): `llm_calls` (N) counted from one FakeModel trajectory's LLM_CALL steps — the step structure is fixed per domain, so one sample is exact.
- 2026-10-12 (T27): no XGBoost/scikit-learn for the value detector — a min/max envelope plus trapezoidal AUC fully measures the value blind spot; a gradient-boosted model is speculative generality this task does not need.
- 2026-10-12 (T27): reused the existing `step.tool_call.result` / `.tool_name` access path (same as crystallizer and runtime/divergence) to walk tool results — no new access path invented.
- 2026-10-12 (T27): the ROC's second domain is `report`, not `ticket` — ticket tool results carry only str/bool leaves, so the numeric value guard is inapplicable there.
- 2026-10-12 (T27): `detection_roc` raises `ValueError` when no numeric field is perturbable — fail loud rather than crash later on a zero-length anomaly set.

## Errors & Fixes

- 2026-10-12 (T-REL): ruff E501 on the two new module heading comments — lines exceeded 88 cols — shortened both headings.
- 2026-10-12 (T27): `ZeroDivisionError` in `detection_roc` on the ticket domain — ticket tool results have only str/bool leaves so the anomaly set was empty — switched the second domain to `report` and added a fail-loud guard for the empty-anomaly case.
- 2026-10-12 (T27): ruff E501 on three new heading/comment lines — exceeded 88 cols — shortened them.

