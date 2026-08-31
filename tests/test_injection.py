from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import (
    HabitPlan,
    cluster_trajectories,
    compile_habit,
    induce_skeleton,
)
from habit.eval import DetectionStats, generate_corpus, run_injection_study
from habit.runtime import expected_tool_fingerprints
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import InvoiceWorkload, MockTool, WorkloadTask

WORKLOAD = InvoiceWorkload()


def _tools() -> dict[str, MockTool]:
    return {tool.name: tool for tool in WORKLOAD.tools()}


def _shape_injector(tools: dict[str, MockTool]) -> dict[str, MockTool]:
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        return {**real(**kwargs), "EXTRA": 1}

    return {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}


def _value_injector(tools: dict[str, MockTool]) -> dict[str, MockTool]:
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        result = real(**kwargs)
        return {**result, "totals_valid": not result["totals_valid"]}

    return {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}


def _plan_and_expected() -> tuple[HabitPlan, list[str | None]]:
    store = SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))
    generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    trajectories = store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = next(
        c
        for c in cluster_trajectories(trajectories)
        if by_id[c.trajectory_ids[0]].domain == "invoice"
    )
    plan = compile_habit(cluster, by_id, _tools()).plan
    expected = expected_tool_fingerprints(induce_skeleton(cluster, by_id))
    return plan, expected


def _study(tasks: list[WorkloadTask]) -> DetectionStats:
    plan, expected = _plan_and_expected()
    return run_injection_study(
        plan,
        expected,
        tasks,
        _tools(),
        shape_injector=_shape_injector,
        value_injector=_value_injector,
    )


def test_rates() -> None:
    tasks = WORKLOAD.generate(20, seed=99)
    stats = _study(tasks)
    assert stats.false_abort_rate == 0.0
    assert stats.shape_catch_rate == 1.0


def test_value_blind_spot() -> None:
    tasks = WORKLOAD.generate(20, seed=99)
    stats = _study(tasks)
    assert stats.value_catch_rate == 0.0


def test_counts() -> None:
    tasks = WORKLOAD.generate(20, seed=99)
    stats = _study(tasks)
    assert stats.normal_runs == stats.shape_runs == stats.value_runs == len(tasks)


def test_determinism() -> None:
    tasks = WORKLOAD.generate(20, seed=99)
    assert _study(tasks) == _study(tasks)
