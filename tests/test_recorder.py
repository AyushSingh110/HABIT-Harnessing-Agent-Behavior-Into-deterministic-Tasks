from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from habit.recorder import TrajectoryRecorder
from habit.schemas import ContextItem, ContextKind, StepType, schema_fingerprint
from habit.storage import SqlAlchemyTrajectoryStore

T0 = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def store(tmp_path: Path) -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )


def _doc(item_id: str) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        kind=ContextKind.DOCUMENT,
        produced_by_step=None,
        content_hash=None,
        size_tokens=None,
    )


def test_llm_then_tool_run(store: SqlAlchemyTrajectoryStore) -> None:
    run = TrajectoryRecorder(store).start_run(
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
        task_input={"id": "INV-1"},
        metadata={},
        started_at=T0,
    )
    run.add_context_item(_doc("doc1"))
    run.record_llm_call(
        provider="groq",
        model="llama-3.3",
        input_tokens=100,
        output_tokens=20,
        context_available=["doc1"],
        context_reads=["doc1"],
        started_at=T0,
        ended_at=T0,
    )
    result = {"total": 42, "lines": [{"sku": "A"}]}
    run.record_tool_call(
        tool_name="fetch",
        call_id="c1",
        arguments={"id": "INV-1"},
        result=result,
        error=None,
        context_available=["doc1"],
        context_reads=[],
        started_at=T0,
        ended_at=T0,
    )
    traj = run.finish(success=True, final_output={"total": 42}, ended_at=T0)

    assert [s.step_index for s in traj.steps] == [0, 1]
    assert traj.steps[1].tool_result_schema_fingerprint == schema_fingerprint(result)


def test_tool_error_result_none_fingerprint(store: SqlAlchemyTrajectoryStore) -> None:
    run = TrajectoryRecorder(store).start_run(
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
        task_input={},
        metadata={},
        started_at=T0,
    )
    run.record_tool_call(
        tool_name="fetch",
        call_id=None,
        arguments={},
        result=None,
        error="boom",
        context_available=[],
        context_reads=[],
        started_at=T0,
        ended_at=T0,
    )
    traj = run.finish(success=False, final_output={}, ended_at=T0, error="boom")
    assert traj.steps[0].tool_result_schema_fingerprint is None


def test_finish_persists(store: SqlAlchemyTrajectoryStore) -> None:
    run = TrajectoryRecorder(store).start_run(
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
        task_input={},
        metadata={},
        started_at=T0,
    )
    run.record_other(context_available=[], context_reads=[], started_at=T0, ended_at=T0)
    traj = run.finish(success=True, final_output={}, ended_at=T0)
    assert store.get("t1") == traj


def test_utc_normalization(store: SqlAlchemyTrajectoryStore) -> None:
    local = datetime(2026, 7, 19, 17, 30, 0, tzinfo=IST)  # 12:00 UTC
    run = TrajectoryRecorder(store).start_run(
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
        task_input={},
        metadata={},
        started_at=local,
    )
    run.record_other(
        context_available=[], context_reads=[], started_at=local, ended_at=local
    )
    traj = run.finish(success=True, final_output={}, ended_at=local)

    assert traj.started_at.tzinfo == timezone.utc
    assert traj.started_at == T0
    assert traj.steps[0].started_at.tzinfo == timezone.utc
    assert traj.steps[0].started_at == T0


def test_context_recorded_per_step(store: SqlAlchemyTrajectoryStore) -> None:
    run = TrajectoryRecorder(store).start_run(
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
        task_input={},
        metadata={},
        started_at=T0,
    )
    run.add_context_item(_doc("a"))
    run.add_context_item(_doc("b"))
    run.record_llm_call(
        provider="groq",
        model="m",
        input_tokens=1,
        output_tokens=1,
        context_available=["a", "b"],
        context_reads=["b"],
        started_at=T0,
        ended_at=T0,
    )
    traj = run.finish(success=True, final_output={}, ended_at=T0)
    assert traj.steps[0].context_available == ["a", "b"]
    assert traj.steps[0].context_reads == ["b"]


def test_step_type_correctness(store: SqlAlchemyTrajectoryStore) -> None:
    run = TrajectoryRecorder(store).start_run(
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
        task_input={},
        metadata={},
        started_at=T0,
    )
    run.record_llm_call(
        provider="groq",
        model="m",
        input_tokens=1,
        output_tokens=1,
        context_available=[],
        context_reads=[],
        started_at=T0,
        ended_at=T0,
    )
    run.record_tool_call(
        tool_name="fetch",
        call_id=None,
        arguments={},
        result={"x": 1},
        error=None,
        context_available=[],
        context_reads=[],
        started_at=T0,
        ended_at=T0,
    )
    run.record_other(context_available=[], context_reads=[], started_at=T0, ended_at=T0)
    traj = run.finish(success=True, final_output={}, ended_at=T0)

    llm, tool, other = traj.steps
    assert (
        llm.step_type == StepType.LLM_CALL
        and llm.llm_call is not None
        and llm.tool_call is None
    )
    assert (
        tool.step_type == StepType.TOOL_CALL
        and tool.tool_call is not None
        and tool.llm_call is None
    )
    assert (
        other.step_type == StepType.OTHER
        and other.llm_call is None
        and other.tool_call is None
    )


def test_independent_runs(store: SqlAlchemyTrajectoryStore) -> None:
    recorder = TrajectoryRecorder(store)
    run_a = recorder.start_run(
        trajectory_id="a",
        domain="invoice",
        task_type="extract",
        task_input={},
        metadata={},
        started_at=T0,
    )
    run_b = recorder.start_run(
        trajectory_id="b",
        domain="invoice",
        task_type="extract",
        task_input={},
        metadata={},
        started_at=T0,
    )
    run_a.record_other(
        context_available=[], context_reads=[], started_at=T0, ended_at=T0
    )
    run_b.record_other(
        context_available=[], context_reads=[], started_at=T0, ended_at=T0
    )
    run_b.record_other(
        context_available=[], context_reads=[], started_at=T0, ended_at=T0
    )
    traj_a = run_a.finish(success=True, final_output={}, ended_at=T0)
    traj_b = run_b.finish(success=True, final_output={}, ended_at=T0)
    assert [s.step_index for s in traj_a.steps] == [0]
    assert [s.step_index for s in traj_b.steps] == [0, 1]


def test_referential_integrity_enforced_at_finish(
    store: SqlAlchemyTrajectoryStore,
) -> None:
    run = TrajectoryRecorder(store).start_run(
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
        task_input={},
        metadata={},
        started_at=T0,
    )
    run.record_llm_call(
        provider="groq",
        model="m",
        input_tokens=1,
        output_tokens=1,
        context_available=["ghost"],
        context_reads=["ghost"],
        started_at=T0,
        ended_at=T0,
    )
    with pytest.raises(ValueError):
        run.finish(success=True, final_output={}, ended_at=T0)
