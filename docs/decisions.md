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

