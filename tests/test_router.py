from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import (
    CompiledHabit,
    TrajectoryCluster,
    ValidationResult,
    cluster_trajectories,
    compile_habit,
    run_habit,
)
from habit.eval import generate_corpus
from habit.runtime import build_router
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import (
    InvoiceWorkload,
    MockTool,
    ReportWorkload,
    TicketWorkload,
    WorkloadGenerator,
)

WORKLOADS: list[WorkloadGenerator] = [
    InvoiceWorkload(),
    TicketWorkload(),
    ReportWorkload(),
]


def _tools(workload: Any) -> dict[str, MockTool]:
    return {tool.name: tool for tool in workload.tools()}


def _cluster_for(trajectories: list[Trajectory], domain: str) -> TrajectoryCluster:
    by_id = {t.trajectory_id: t for t in trajectories}
    for cluster in cluster_trajectories(trajectories):
        if by_id[cluster.trajectory_ids[0]].domain == domain:
            return cluster
    raise AssertionError(domain)


def _compiled(tmp_path: Path) -> dict[str, CompiledHabit]:
    store = SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )
    generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    trajectories = store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    return {
        workload.domain: compile_habit(
            _cluster_for(trajectories, workload.domain), by_id, _tools(workload)
        )
        for workload in WORKLOADS
    }


def test_routes_usable_habits(tmp_path: Path) -> None:
    router = build_router(_compiled(tmp_path))
    assert set(router.habits) == {"invoice", "ticket", "report"}
    workload = InvoiceWorkload()
    tools = _tools(workload)
    checker = workload.checker()
    for task in workload.generate(10, seed=99):
        plan = router.route("invoice", task.task_input)
        assert plan is not None
        assert checker(task, run_habit(plan, task.task_input, tools)) is True


def test_unknown_domain_returns_none(tmp_path: Path) -> None:
    router = build_router(_compiled(tmp_path))
    assert router.route("unknown", {"anything": 1}) is None


def test_unusable_habit_not_registered(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    failed = ValidationResult(checked=3, matched=0, mismatched_ids=("x",), passed=False)
    compiled["invoice"] = CompiledHabit(
        plan=compiled["invoice"].plan, validation=failed
    )
    router = build_router(compiled)
    assert "invoice" not in router.habits
    assert router.route("invoice", {}) is None


def test_inapplicable_task_returns_none(tmp_path: Path) -> None:
    router = build_router(_compiled(tmp_path))
    task = InvoiceWorkload().generate(1, seed=5)[0]
    partial = dict(task.task_input)
    del partial["vendor"]
    assert router.route("invoice", partial) is None
    assert router.route("invoice", task.task_input) is not None


def test_determinism(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    a = build_router(compiled)
    b = build_router(compiled)
    assert a.habits == b.habits
    task = InvoiceWorkload().generate(1, seed=5)[0]
    assert a.route("invoice", task.task_input) == b.route("invoice", task.task_input)
