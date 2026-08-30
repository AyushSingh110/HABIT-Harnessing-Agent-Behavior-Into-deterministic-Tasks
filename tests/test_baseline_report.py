from pathlib import Path

import pytest
from sqlalchemy import create_engine

from habit.baseline import FakeModel, run_report_baseline
from habit.schemas import StepType
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import MockTool, ReportWorkload

STEP_SEQUENCE = [
    StepType.LLM_CALL,
    StepType.TOOL_CALL,
    StepType.LLM_CALL,
    StepType.TOOL_CALL,
    StepType.LLM_CALL,
    StepType.TOOL_CALL,
    StepType.LLM_CALL,
    StepType.TOOL_CALL,
    StepType.LLM_CALL,
    StepType.TOOL_CALL,
    StepType.LLM_CALL,
]


@pytest.fixture
def store(tmp_path: Path) -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )


def _tools() -> dict[str, MockTool]:
    return {tool.name: tool for tool in ReportWorkload().tools()}


def test_persisted_and_domain(store: SqlAlchemyTrajectoryStore) -> None:
    task = ReportWorkload().generate(1, seed=1)[0]
    traj = run_report_baseline(
        task, model=FakeModel(), store=store, tools=_tools(), trajectory_id="t1"
    )
    assert traj.domain == "report"
    assert store.get("t1") == traj


def test_step_sequence(store: SqlAlchemyTrajectoryStore) -> None:
    task = ReportWorkload().generate(1, seed=1)[0]
    traj = run_report_baseline(
        task, model=FakeModel(), store=store, tools=_tools(), trajectory_id="t1"
    )
    assert [s.step_type for s in traj.steps] == STEP_SEQUENCE


def test_fingerprints(store: SqlAlchemyTrajectoryStore) -> None:
    task = ReportWorkload().generate(1, seed=1)[0]
    traj = run_report_baseline(
        task, model=FakeModel(), store=store, tools=_tools(), trajectory_id="t1"
    )
    for step in traj.steps:
        if step.step_type == StepType.TOOL_CALL:
            assert step.tool_result_schema_fingerprint is not None
        else:
            assert step.tool_result_schema_fingerprint is None


def test_faithful_reads(store: SqlAlchemyTrajectoryStore) -> None:
    task = ReportWorkload().generate(1, seed=1)[0]
    traj = run_report_baseline(
        task, model=FakeModel(), store=store, tools=_tools(), trajectory_id="t1"
    )
    assert traj.steps[3].context_reads == ["request", "raw_records"]
    for step in traj.steps:
        assert set(step.context_reads) <= set(step.context_available)


def test_ground_truth_match_over_batch(store: SqlAlchemyTrajectoryStore) -> None:
    tasks = ReportWorkload().generate(20, seed=13)
    filtering_seen = False
    for i, task in enumerate(tasks):
        traj = run_report_baseline(
            task, model=FakeModel(), store=store, tools=_tools(), trajectory_id=f"t{i}"
        )
        assert traj.outcome.ground_truth_match is True
        filtering_seen = filtering_seen or (
            task.expected["record_count"] < len(task.task_input["records"])
        )
    assert filtering_seen


def test_structural_determinism(store: SqlAlchemyTrajectoryStore) -> None:
    task = ReportWorkload().generate(1, seed=1)[0]
    a = run_report_baseline(
        task, model=FakeModel(), store=store, tools=_tools(), trajectory_id="a"
    )
    b = run_report_baseline(
        task, model=FakeModel(), store=store, tools=_tools(), trajectory_id="b"
    )
    assert [s.step_type for s in a.steps] == [s.step_type for s in b.steps]
    assert [s.context_reads for s in a.steps] == [s.context_reads for s in b.steps]
    a_tools = [s.tool_call.tool_name for s in a.steps if s.tool_call]
    b_tools = [s.tool_call.tool_name for s in b.steps if s.tool_call]
    assert a_tools == b_tools
