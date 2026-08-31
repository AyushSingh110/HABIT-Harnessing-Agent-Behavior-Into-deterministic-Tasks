from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel, run_invoice_baseline
from habit.compiler import (
    HabitPlan,
    cluster_trajectories,
    compile_habit,
    induce_skeleton,
)
from habit.runtime import DriftMonitor, expected_tool_fingerprints, run_habit_checked
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import InvoiceWorkload, MockTool

WORKLOAD = InvoiceWorkload()


def _tools() -> dict[str, MockTool]:
    return {tool.name: tool for tool in WORKLOAD.tools()}


def _drifted_tools() -> dict[str, MockTool]:
    tools = _tools()
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        return {**real(**kwargs), "EXTRA": 1}

    return {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}


def test_all_habit_not_drifting() -> None:
    monitor = DriftMonitor(window=5, threshold=0.5)
    for _ in range(5):
        monitor.record("habit")
    assert monitor.is_drifting() is False


def test_majority_fallback_drifts() -> None:
    monitor = DriftMonitor(window=4, threshold=0.5)
    for mode in ("fallback", "fallback", "fallback", "habit"):
        monitor.record(mode)
    assert monitor.is_drifting() is True


def test_live_only_not_drifting() -> None:
    monitor = DriftMonitor(window=4, threshold=0.5)
    for _ in range(4):
        monitor.record("live")
    assert monitor.is_drifting() is False


def test_threshold_boundary_excludes_equal() -> None:
    monitor = DriftMonitor(window=4, threshold=0.5)
    for mode in ("fallback", "fallback", "habit", "habit"):
        monitor.record(mode)
    assert monitor.is_drifting() is False


def test_window_slides_clears_flag() -> None:
    monitor = DriftMonitor(window=4, threshold=0.5)
    for _ in range(4):
        monitor.record("fallback")
    assert monitor.is_drifting() is True
    for _ in range(4):
        monitor.record("habit")
    assert monitor.is_drifting() is False


def _compile_from(
    trajectories: list[Trajectory], tools: dict[str, MockTool]
) -> tuple[HabitPlan, list[str | None]]:
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = next(
        c
        for c in cluster_trajectories(trajectories)
        if by_id[c.trajectory_ids[0]].domain == "invoice"
    )
    plan = compile_habit(cluster, by_id, tools).plan
    expected = expected_tool_fingerprints(induce_skeleton(cluster, by_id))
    return plan, expected


def _record_batch(
    tasks: list[Any], tools: dict[str, MockTool], tag: str
) -> list[Trajectory]:
    store = SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))
    for i, task in enumerate(tasks):
        run_invoice_baseline(
            task,
            model=FakeModel(),
            store=store,
            tools=tools,
            trajectory_id=f"{tag}-{i}",
        )
    return store.query()


def test_recompile_resolves_drift() -> None:
    # OLD world habit
    old_traj = _record_batch(WORKLOAD.generate(20, seed=1), _tools(), "old")
    plan_v1, expected_v1 = _compile_from(old_traj, _tools())

    tools_v2 = _drifted_tools()
    monitor = DriftMonitor(window=10, threshold=0.5)

    # DRIFT: v1 keeps diverging on the changed world
    for task in WORKLOAD.generate(10, seed=200):
        _, report = run_habit_checked(plan_v1, expected_v1, task.task_input, tools_v2)
        assert report.diverged is True
        monitor.record("fallback")
    assert monitor.is_drifting() is True

    # RECOMPILE from new-world trajectories (the live agent adapts to tools_v2)
    new_traj = _record_batch(WORKLOAD.generate(20, seed=300), tools_v2, "new")
    plan_v2, expected_v2 = _compile_from(new_traj, tools_v2)

    checker = WORKLOAD.checker()
    for task in WORKLOAD.generate(10, seed=400):
        output, report = run_habit_checked(
            plan_v2, expected_v2, task.task_input, tools_v2
        )
        assert report.diverged is False
        assert output is not None
        assert checker(task, output) is True
        # v1 still diverges on the same drifted world
        _, old_report = run_habit_checked(
            plan_v1, expected_v1, task.task_input, tools_v2
        )
        assert old_report.diverged is True
