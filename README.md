# HABIT — Harnessing Agent Behavior Into deterministic Tasks

**Muscle memory for AI agents — decide once, execute forever.**

HABIT is a self-optimizing runtime for LLM agents. It records agent runs as structured
trajectories, compiles repeated behavior into deterministic code ("habits"), induces per-step
context policies from observed access patterns, and at runtime routes tasks to habits while
detecting mid-run divergence and falling back to the live LLM agent.

## Architecture

HABIT is organized into four layers with strict boundaries:

| Layer | Package | Responsibility |
| --- | --- | --- |
| 1 — Recorder | `habit.recorder` | Wrap an agent framework, emit validated `Trajectory` objects, persist them. |
| 2 — Compiler | `habit.compiler` | Cluster trajectories, induce stable skeletons, generate deterministic habits, replay-validate them. |
| 3 — Context | `habit.context` | Induce per-step context policies from access patterns; paging and prefetch. |
| 4 — Runtime | `habit.runtime` | Route tasks to habits or the live agent, detect divergence, fall back safely, trigger recompilation on drift. |

Supporting modules: `habit.schemas` (frozen data contracts), `habit.interfaces` (cross-layer
protocols), plus adapters, workloads, and eval harnesses added in later phases.

## Status

Currently at Foundation phase. The data contracts and storage interface that every layer depends on are in
place and fully tested; the four layers themselves are not yet implemented.

### Completed

- **Project skeleton** — `src`-layout package, hatchling build, PEP 561 typed marker.
  `pip install -e ".[dev]"` and `import habit` both work. CI runs `ruff` → `mypy` (strict) →
  `pytest` on Python 3.11.
- **Trajectory schema** (`habit.schemas`) — the frozen Pydantic v2 record of one agent run:
  `Trajectory`, `Step`, `LLMCall`, `ToolCall`, `ContextItem`, `Outcome`, and the `StepType` /
  `ContextKind` enums. Enforces step-payload invariants, tool-result fingerprint invariants,
  referential integrity across context items, and timezone-aware timestamps. Round-trips
  losslessly through JSON and dicts. Field names align to OpenTelemetry GenAI semantic
  conventions (see [docs/otel_mapping.md](docs/otel_mapping.md)).
- **Structure fingerprint** (`habit.schemas.schema_fingerprint`) — a deterministic,
  value-independent hash of a tool result's key/type structure. Stable across values, key order,
  and list length; the signal the future divergence detector (Layer 4) will compare against.
- **Storage interface** (`habit.interfaces.TrajectoryStore`) — a backend-agnostic,
  `@runtime_checkable` protocol for persisting and querying trajectories (`save`, `get`, `query`,
  `count` with AND-filter semantics), verified implementable by a typed in-memory double.

### Not yet started

Recorder, storage backend (SQLAlchemy / SQLite / PostgreSQL), compiler, context policies, runtime
router and divergence detector, framework adapters, workloads, and the evaluation benchmark.

## Development

Requires Python 3.11+.

```bash
pip install -e ".[dev]"

ruff check src tests
mypy
pytest -q
```

All tests run offline with no API key and no network access.

## Design notes

Significant decisions not dictated by a task are recorded in
[docs/decisions.md](docs/decisions.md).
