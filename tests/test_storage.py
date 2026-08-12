from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from habit.interfaces import TrajectoryStore
from habit.schemas import (
    ContextItem,
    ContextKind,
    LLMCall,
    Outcome,
    Step,
    StepType,
    ToolCall,
    Trajectory,
    schema_fingerprint,
)
from habit.storage import SqlAlchemyTrajectoryStore, engine_from_env

T0 = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)


def _make_rich_trajectory(
    trajectory_id: str = "rich-1",
    *,
    domain: str = "invoice",
    task_type: str = "extract",
    success: bool = True,
    started_at: datetime = T0,
) -> Trajectory:
    ctx1 = ContextItem(
        item_id="doc1",
        kind=ContextKind.DOCUMENT,
        produced_by_step=None,
        content_hash="hash1",
        size_tokens=100,
    )
    ctx2 = ContextItem(
        item_id="tool1",
        kind=ContextKind.TOOL_RESULT,
        produced_by_step=1,
        content_hash="hash2",
        size_tokens=50,
    )

    tool_res = {"vendor": "Acme Corp", "total": 250.0}
    fp = schema_fingerprint(tool_res)

    step0 = Step(
        step_index=0,
        step_type=StepType.LLM_CALL,
        llm_call=LLMCall(
            provider="groq", model="llama-3.3-70b", input_tokens=100, output_tokens=20
        ),
        tool_call=None,
        tool_result_schema_fingerprint=None,
        context_available=["doc1"],
        context_reads=["doc1"],
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=1),
    )

    step1 = Step(
        step_index=1,
        step_type=StepType.TOOL_CALL,
        llm_call=None,
        tool_call=ToolCall(
            tool_name="extract_fields",
            call_id="call_1",
            arguments={"file_path": "inv.pdf"},
            result=tool_res,
            error=None,
        ),
        tool_result_schema_fingerprint=fp,
        context_available=["doc1", "tool1"],
        context_reads=["tool1"],
        started_at=started_at + timedelta(seconds=1),
        ended_at=started_at + timedelta(seconds=2),
    )

    return Trajectory(
        trajectory_id=trajectory_id,
        domain=domain,
        task_type=task_type,
        task_input={"file": "inv.pdf"},
        context_items=[ctx1, ctx2],
        steps=[step0, step1],
        outcome=Outcome(
            success=success,
            final_output={"extracted": True},
            error=None if success else "Failed extraction",
            ground_truth_match=success,
        ),
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=2),
        metadata={"env": "test"},
    )


def test_static_conformance(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    store: TrajectoryStore = SqlAlchemyTrajectoryStore(engine)
    assert isinstance(store, TrajectoryStore)


def test_save_and_get_rich_trajectory(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    store = SqlAlchemyTrajectoryStore(engine)
    traj = _make_rich_trajectory()

    store.save(traj)
    fetched = store.get("rich-1")

    assert fetched is not None
    assert fetched == traj
    assert fetched.started_at.tzinfo is not None


def test_get_unknown_returns_none(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    store = SqlAlchemyTrajectoryStore(engine)
    assert store.get("unknown-id") is None


def test_save_duplicate_raises_value_error(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    store = SqlAlchemyTrajectoryStore(engine)
    traj = _make_rich_trajectory("dup-1")

    store.save(traj)
    with pytest.raises(ValueError, match="trajectory_id already exists"):
        store.save(traj)


def test_query_and_filtering(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    store = SqlAlchemyTrajectoryStore(engine)

    t1 = _make_rich_trajectory("t1", domain="invoice", task_type="extract")
    t2 = _make_rich_trajectory("t2", domain="invoice", task_type="verify")
    t3 = _make_rich_trajectory("t3", domain="ticket", task_type="extract")

    store.save(t1)
    store.save(t2)
    store.save(t3)

    res_domain = store.query(domain="invoice")
    assert [t.trajectory_id for t in res_domain] == ["t1", "t2"]

    res_type = store.query(task_type="extract")
    assert [t.trajectory_id for t in res_type] == ["t1", "t3"]

    res_combined = store.query(domain="invoice", task_type="extract")
    assert [t.trajectory_id for t in res_combined] == ["t1"]


def test_query_success_filter(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    store = SqlAlchemyTrajectoryStore(engine)

    t_ok = _make_rich_trajectory("t-ok", success=True)
    t_fail = _make_rich_trajectory("t-fail", success=False)

    store.save(t_ok)
    store.save(t_fail)

    res_fail = store.query(success=False)
    assert [t.trajectory_id for t in res_fail] == ["t-fail"]

    res_ok = store.query(success=True)
    assert [t.trajectory_id for t in res_ok] == ["t-ok"]


def test_query_ordering_and_limit(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    store = SqlAlchemyTrajectoryStore(engine)

    t_late = _make_rich_trajectory("late", started_at=T0 + timedelta(hours=2))
    t_early = _make_rich_trajectory("early", started_at=T0)
    t_mid = _make_rich_trajectory("mid", started_at=T0 + timedelta(hours=1))

    store.save(t_late)
    store.save(t_early)
    store.save(t_mid)

    res = store.query()
    assert [t.trajectory_id for t in res] == ["early", "mid", "late"]

    res_limit = store.query(limit=2)
    assert [t.trajectory_id for t in res_limit] == ["early", "mid"]


def test_count_matches_query(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    store = SqlAlchemyTrajectoryStore(engine)

    store.save(_make_rich_trajectory("t1", domain="invoice", success=True))
    store.save(_make_rich_trajectory("t2", domain="invoice", success=False))
    store.save(_make_rich_trajectory("t3", domain="ticket", success=True))

    assert store.count(domain="invoice") == len(store.query(domain="invoice"))
    assert store.count(domain="invoice", success=True) == len(
        store.query(domain="invoice", success=True)
    )
    assert store.count(domain="ticket") == len(store.query(domain="ticket"))


def test_engine_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    default_engine = engine_from_env()
    assert default_engine.url.render_as_string(hide_password=False) == "sqlite:///habit.db"

    custom_url = f"sqlite:///{tmp_path}/custom.db"
    monkeypatch.setenv("DATABASE_URL", custom_url)
    custom_engine = engine_from_env()
    assert custom_engine.url.render_as_string(hide_password=False) == custom_url
