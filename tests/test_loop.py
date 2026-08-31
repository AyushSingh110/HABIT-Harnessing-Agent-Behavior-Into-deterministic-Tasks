from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel, run_invoice_baseline
from habit.compiler import cluster_trajectories, compile_habit, induce_skeleton
from habit.eval import generate_corpus
from habit.runtime import (
    Router,
    build_router,
    expected_tool_fingerprints,
    run_task,
)
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import InvoiceWorkload, MockTool

WORKLOAD = InvoiceWorkload()


def _store(tmp_path: Path, name: str) -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(create_engine(f"sqlite:///{tmp_path / name}"))


def _tools() -> dict[str, MockTool]:
    return {tool.name: tool for tool in WORKLOAD.tools()}


def _setup(tmp_path: Path) -> tuple[Router, list[str | None]]:
    store = _store(tmp_path, "train.db")
    generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    trajectories: list[Trajectory] = store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = next(
        c
        for c in cluster_trajectories(trajectories)
        if by_id[c.trajectory_ids[0]].domain == "invoice"
    )
    compiled = compile_habit(cluster, by_id, _tools())
    router = build_router({"invoice": compiled})
    expected = expected_tool_fingerprints(induce_skeleton(cluster, by_id))
    return router, expected


def test_habit_path(tmp_path: Path) -> None:
    router, expected = _setup(tmp_path)
    task = WORKLOAD.generate(1, seed=5)[0]
    result = run_task(
        domain="invoice",
        task=task,
        trajectory_id="r1",
        router=router,
        expected=expected,
        tools=_tools(),
        baseline=run_invoice_baseline,
        model=FakeModel(),
        store=_store(tmp_path, "run.db"),
    )
    assert result.mode == "habit"
    assert WORKLOAD.checker()(task, result.output) is True


def test_fallback_path(tmp_path: Path) -> None:
    router, expected = _setup(tmp_path)
    tools = _tools()
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        result = dict(real(**kwargs))
        result["EXTRA"] = 1
        return result

    tampered = {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}
    task = WORKLOAD.generate(1, seed=5)[0]
    result = run_task(
        domain="invoice",
        task=task,
        trajectory_id="r1",
        router=router,
        expected=expected,
        tools=tampered,
        baseline=run_invoice_baseline,
        model=FakeModel(),
        store=_store(tmp_path, "run.db"),
    )
    assert result.mode == "fallback"
    assert WORKLOAD.checker()(task, result.output) is True


def test_live_path(tmp_path: Path) -> None:
    _, expected = _setup(tmp_path)
    empty_router = build_router({})
    task = WORKLOAD.generate(1, seed=5)[0]
    result = run_task(
        domain="invoice",
        task=task,
        trajectory_id="r1",
        router=empty_router,
        expected=expected,
        tools=_tools(),
        baseline=run_invoice_baseline,
        model=FakeModel(),
        store=_store(tmp_path, "run.db"),
    )
    assert result.mode == "live"
    assert WORKLOAD.checker()(task, result.output) is True


def test_habit_equals_live(tmp_path: Path) -> None:
    router, expected = _setup(tmp_path)
    task = WORKLOAD.generate(1, seed=5)[0]
    habit_result = run_task(
        domain="invoice",
        task=task,
        trajectory_id="r1",
        router=router,
        expected=expected,
        tools=_tools(),
        baseline=run_invoice_baseline,
        model=FakeModel(),
        store=_store(tmp_path, "run.db"),
    )
    live_traj = run_invoice_baseline(
        task,
        model=FakeModel(),
        store=_store(tmp_path, "live.db"),
        tools=_tools(),
        trajectory_id="live",
    )
    assert habit_result.mode == "habit"
    assert habit_result.output == live_traj.outcome.final_output


def test_determinism(tmp_path: Path) -> None:
    router, expected = _setup(tmp_path)
    task = WORKLOAD.generate(1, seed=5)[0]

    def once(name: str) -> tuple[str, dict[str, Any]]:
        result = run_task(
            domain="invoice",
            task=task,
            trajectory_id="r1",
            router=router,
            expected=expected,
            tools=_tools(),
            baseline=run_invoice_baseline,
            model=FakeModel(),
            store=_store(tmp_path, name),
        )
        return result.mode, result.output

    assert once("a.db") == once("b.db")
