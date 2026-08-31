from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import (
    HabitPlan,
    Skeleton,
    TrajectoryCluster,
    cluster_trajectories,
    compile_habit,
    induce_skeleton,
)
from habit.eval import generate_corpus
from habit.runtime import expected_tool_fingerprints, run_habit_checked
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import InvoiceWorkload, MockTool, ReportWorkload


def _cluster_for(trajectories: list[Trajectory], domain: str) -> TrajectoryCluster:
    by_id = {t.trajectory_id: t for t in trajectories}
    for cluster in cluster_trajectories(trajectories):
        if by_id[cluster.trajectory_ids[0]].domain == domain:
            return cluster
    raise AssertionError(domain)


def _tools(workload: Any) -> dict[str, MockTool]:
    return {tool.name: tool for tool in workload.tools()}


def _compiled(tmp_path: Path, domain: str, workload: Any) -> tuple[HabitPlan, Skeleton]:
    store = SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )
    generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    trajectories = store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = _cluster_for(trajectories, domain)
    plan = compile_habit(cluster, by_id, _tools(workload)).plan
    skeleton = induce_skeleton(cluster, by_id)
    return plan, skeleton


def test_clean_run_no_divergence(tmp_path: Path) -> None:
    workload = ReportWorkload()
    plan, skeleton = _compiled(tmp_path, "report", workload)
    expected = expected_tool_fingerprints(skeleton)
    tools = _tools(workload)
    checker = workload.checker()
    for task in workload.generate(15, seed=99):
        output, report = run_habit_checked(plan, expected, task.task_input, tools)
        assert report.diverged is False
        assert output is not None
        assert checker(task, output) is True


def test_shape_divergence_detected(tmp_path: Path) -> None:
    workload = InvoiceWorkload()
    plan, skeleton = _compiled(tmp_path, "invoice", workload)
    expected = expected_tool_fingerprints(skeleton)
    tools = _tools(workload)
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        result = dict(real(**kwargs))
        result["EXTRA"] = 1
        return result

    tampered = {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}
    task = workload.generate(1, seed=5)[0]
    output, report = run_habit_checked(plan, expected, task.task_input, tampered)
    assert report.diverged is True
    assert report.tool_name == "validate_totals"
    assert report.expected_fingerprint != report.actual_fingerprint
    assert output is None


def test_failure_divergence(tmp_path: Path) -> None:
    workload = ReportWorkload()
    plan, skeleton = _compiled(tmp_path, "report", workload)
    expected = expected_tool_fingerprints(skeleton)
    tools = _tools(workload)
    real = tools["aggregate"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        result = dict(real(**kwargs))
        del result["totals"]
        return result

    tampered = {**tools, "aggregate": MockTool(name="aggregate", fn=bad)}
    task = workload.generate(1, seed=5)[0]
    output, report = run_habit_checked(plan, expected, task.task_input, tampered)
    assert report.diverged is True
    assert output is None


def test_expected_alignment(tmp_path: Path) -> None:
    workload = InvoiceWorkload()
    plan, skeleton = _compiled(tmp_path, "invoice", workload)
    expected = expected_tool_fingerprints(skeleton)
    assert len(expected) == len(plan.steps)
    assert all(fp is not None for fp in expected)


def test_determinism(tmp_path: Path) -> None:
    workload = InvoiceWorkload()
    plan, skeleton = _compiled(tmp_path, "invoice", workload)
    expected = expected_tool_fingerprints(skeleton)
    tools = _tools(workload)
    task = workload.generate(1, seed=5)[0]
    _, a = run_habit_checked(plan, expected, task.task_input, tools)
    _, b = run_habit_checked(plan, expected, task.task_input, tools)
    assert a == b
