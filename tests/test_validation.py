import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import (
    CompiledHabit,
    InputField,
    TrajectoryCluster,
    cluster_trajectories,
    compile_habit,
    crystallize,
    validate_habit,
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
from habit.workloads import InvoiceWorkload, MockTool, ReportWorkload, TicketWorkload

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


def test_invoice_compiles_and_usable(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    habit = compile_habit(
        _cluster_for(trajectories, "invoice"), by_id, _tools(InvoiceWorkload())
    )
    assert habit.usable is True
    assert habit.validation.checked > 0
    assert habit.validation.matched == habit.validation.checked
    assert habit.validation.mismatched_ids == ()


def test_validation_set_held_out(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = _cluster_for(trajectories, "invoice")
    habit = compile_habit(
        cluster, by_id, _tools(InvoiceWorkload()), validation_fraction=0.3
    )
    assert habit.validation.checked == 6
    expected_held_out = sorted(cluster.trajectory_ids)[:6]
    assert len(expected_held_out) == 6
    # all held-out are baseline-correct so all 6 are checked and matched
    assert habit.validation.matched == 6


def test_all_domains_usable(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    for workload in (InvoiceWorkload(), TicketWorkload(), ReportWorkload()):
        habit = compile_habit(
            _cluster_for(trajectories, workload.domain), by_id, _tools(workload)
        )
        assert habit.usable is True


def test_broken_plan_rejected(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = _cluster_for(trajectories, "invoice")
    ids = sorted(cluster.trajectory_ids)
    plan = crystallize(cluster, by_id)
    broken = dataclasses.replace(
        plan,
        output_assembly={**plan.output_assembly, "total": InputField("invoice_id")},
    )
    held_out = [by_id[tid] for tid in ids[:6]]
    result = validate_habit(broken, held_out, _tools(InvoiceWorkload()))
    assert result.passed is False
    assert result.mismatched_ids
    assert CompiledHabit(plan=broken, validation=result).usable is False


def _synthetic(trajectory_id: str, match: bool) -> Trajectory:
    step = Step(
        step_index=0,
        step_type=StepType.TOOL_CALL,
        llm_call=None,
        tool_call=ToolCall(
            tool_name="echo",
            call_id=None,
            arguments={"x": 1},
            result={"y": 1},
            error=None,
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
        task_input={"x": 1},
        context_items=[],
        steps=[step],
        outcome=Outcome(
            success=True, final_output={"y": 1}, error=None, ground_truth_match=match
        ),
        started_at=T0,
        ended_at=T0,
        metadata={},
    )


def test_baseline_wrong_excluded() -> None:
    good = _synthetic("good", True)
    bad = _synthetic("bad", False)
    cluster = TrajectoryCluster(
        signature=(("TOOL_CALL", "echo"),), trajectory_ids=["good"]
    )
    plan = crystallize(cluster, {"good": good})
    tools = {"echo": MockTool(name="echo", fn=lambda x: {"y": x})}
    result = validate_habit(plan, [good, bad], tools)
    assert result.checked == 1
    assert result.matched == 1


def test_determinism(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path, 20)
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = _cluster_for(trajectories, "invoice")
    tools = _tools(InvoiceWorkload())
    assert compile_habit(cluster, by_id, tools) == compile_habit(cluster, by_id, tools)
