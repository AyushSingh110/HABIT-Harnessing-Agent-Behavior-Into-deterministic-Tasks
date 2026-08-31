from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import (
    HabitPlan,
    InputField,
    ResultField,
    TrajectoryCluster,
    cluster_trajectories,
    crystallize,
    run_habit,
    structural_signature,
)
from habit.eval import generate_corpus
from habit.schemas import (
    Outcome,
    Step,
    StepType,
    ToolCall,
    Trajectory,
    schema_fingerprint,
)
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import (
    InvoiceWorkload,
    MockTool,
    ReportWorkload,
    TicketWorkload,
)

T0 = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def _corpus(tmp_path: Path, per_domain: int) -> list[Trajectory]:
    store = SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )
    generate_corpus(store, model=FakeModel(), per_domain=per_domain, seed=1)
    return store.query()


def _cluster_for(trajectories: list[Trajectory], domain: str) -> TrajectoryCluster:
    by_id = {t.trajectory_id: t for t in trajectories}
    for cluster in cluster_trajectories(trajectories):
        if by_id[cluster.trajectory_ids[0]].domain == domain:
            return cluster
    raise AssertionError(domain)


def _tools(workload: Any) -> dict[str, MockTool]:
    return {tool.name: tool for tool in workload.tools()}


def test_invoice_plan_shape(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    plan = crystallize(_cluster_for(trajectories, "invoice"), by_id)
    assert plan.domain == "invoice"
    assert [s.tool_name for s in plan.steps] == [
        "extract_header",
        "extract_line_items",
        "validate_totals",
        "lookup_vendor",
    ]
    assert set(plan.output_assembly) == {
        "invoice_id",
        "vendor",
        "total",
        "line_item_count",
        "totals_valid",
        "vendor_known",
    }


def test_invoice_correctness(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    plan = crystallize(_cluster_for(trajectories, "invoice"), by_id)
    workload = InvoiceWorkload()
    checker = workload.checker()
    tools = _tools(workload)
    tasks = workload.generate(20, seed=1)
    invalid_seen = False
    for task in tasks:
        output = run_habit(plan, task.task_input, tools)
        assert checker(task, output) is True
        invalid_seen = invalid_seen or not task.expected["totals_valid"]
    assert invalid_seen


def test_induced_sources(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    plan = crystallize(_cluster_for(trajectories, "invoice"), by_id)
    # extract_line_items is tool ordinal 1; its result "count" feeds line_item_count.
    assert plan.output_assembly["line_item_count"] == ResultField(1, "count")
    # lookup_vendor's vendor arg resolves to task_input["vendor"] (InputField wins).
    vendor_step = next(s for s in plan.steps if s.tool_name == "lookup_vendor")
    assert vendor_step.arg_sources["vendor"] == InputField("vendor")


def test_ticket_and_report_correctness(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    for workload in (TicketWorkload(), ReportWorkload()):
        plan = crystallize(_cluster_for(trajectories, workload.domain), by_id)
        checker = workload.checker()
        tools = _tools(workload)
        for task in workload.generate(20, seed=1):
            output = run_habit(plan, task.task_input, tools)
            assert checker(task, output) is True


def test_report_aggregate_records_source(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    plan = crystallize(_cluster_for(trajectories, "report"), by_id)
    aggregate_step = next(s for s in plan.steps if s.tool_name == "aggregate")
    # filter_records is tool ordinal 1; aggregate consumes its filtered "records".
    assert aggregate_step.arg_sources["records"] == ResultField(1, "records")


def test_determinism(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = _cluster_for(trajectories, "invoice")
    assert crystallize(cluster, by_id) == crystallize(cluster, by_id)


def _unexplainable_trajectory(trajectory_id: str, x: int) -> Trajectory:
    step = Step(
        step_index=0,
        step_type=StepType.TOOL_CALL,
        llm_call=None,
        tool_call=ToolCall(
            tool_name="t", call_id=None, arguments={"x": x}, result={"y": 1}, error=None
        ),
        tool_result_schema_fingerprint=schema_fingerprint({"y": 1}),
        context_available=[],
        context_reads=[],
        started_at=T0,
        ended_at=T0,
    )
    return Trajectory(
        trajectory_id=trajectory_id,
        domain="synthetic",
        task_type="t",
        task_input={},
        context_items=[],
        steps=[step],
        outcome=Outcome(
            success=True, final_output={}, error=None, ground_truth_match=None
        ),
        started_at=T0,
        ended_at=T0,
        metadata={},
    )


def test_unexplainable_argument_raises() -> None:
    a = _unexplainable_trajectory("a", 1)
    b = _unexplainable_trajectory("b", 2)
    cluster = TrajectoryCluster(
        signature=structural_signature(a), trajectory_ids=["a", "b"]
    )
    with pytest.raises(ValueError):
        crystallize(cluster, {"a": a, "b": b})


def test_plan_is_habitplan(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    assert isinstance(
        crystallize(_cluster_for(trajectories, "invoice"), by_id), HabitPlan
    )
