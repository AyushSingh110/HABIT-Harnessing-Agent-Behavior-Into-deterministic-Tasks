from datetime import datetime, timedelta, timezone

import pytest

from habit.interfaces import TrajectoryStore
from habit.schemas import Outcome, Trajectory

T0 = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


# Typed in-memory test double proving TrajectoryStore is implementable.
class _DictStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Trajectory] = {}

    def save(self, trajectory: Trajectory) -> None:
        if trajectory.trajectory_id in self._by_id:
            raise ValueError(f"trajectory_id exists: {trajectory.trajectory_id}")
        self._by_id[trajectory.trajectory_id] = trajectory

    def get(self, trajectory_id: str) -> Trajectory | None:
        return self._by_id.get(trajectory_id)

    def query(
        self,
        *,
        domain: str | None = None,
        task_type: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
    ) -> list[Trajectory]:
        matches = [
            t
            for t in self._by_id.values()
            if (domain is None or t.domain == domain)
            and (task_type is None or t.task_type == task_type)
            and (success is None or t.outcome.success == success)
        ]
        matches.sort(key=lambda t: t.started_at)
        return matches if limit is None else matches[:limit]

    def count(
        self,
        *,
        domain: str | None = None,
        task_type: str | None = None,
        success: bool | None = None,
    ) -> int:
        return len(self.query(domain=domain, task_type=task_type, success=success))


def _trajectory(
    trajectory_id: str,
    *,
    domain: str = "invoice",
    task_type: str = "extract",
    success: bool = True,
    started_at: datetime = T0,
) -> Trajectory:
    return Trajectory(
        trajectory_id=trajectory_id,
        domain=domain,
        task_type=task_type,
        task_input={},
        context_items=[],
        steps=[],
        outcome=Outcome(
            success=success, final_output={}, error=None, ground_truth_match=None
        ),
        started_at=started_at,
        ended_at=started_at,
        metadata={},
    )


def test_runtime_checkable() -> None:
    assert isinstance(_DictStore(), TrajectoryStore)


def test_save_then_get() -> None:
    store = _DictStore()
    traj = _trajectory("t1")
    store.save(traj)
    assert store.get("t1") == traj


def test_get_unknown_returns_none() -> None:
    assert _DictStore().get("nope") is None


def test_save_duplicate_raises() -> None:
    store = _DictStore()
    store.save(_trajectory("t1"))
    with pytest.raises(ValueError):
        store.save(_trajectory("t1"))


def test_query_domain_filter() -> None:
    store = _DictStore()
    store.save(_trajectory("t1", domain="invoice"))
    store.save(_trajectory("t2", domain="ticket"))
    result = store.query(domain="invoice")
    assert [t.trajectory_id for t in result] == ["t1"]


def test_query_success_filter() -> None:
    store = _DictStore()
    store.save(_trajectory("ok", success=True))
    store.save(_trajectory("bad", success=False))
    result = store.query(success=False)
    assert [t.trajectory_id for t in result] == ["bad"]


def test_query_order_and_limit() -> None:
    store = _DictStore()
    store.save(_trajectory("late", started_at=T0 + timedelta(hours=2)))
    store.save(_trajectory("early", started_at=T0))
    store.save(_trajectory("mid", started_at=T0 + timedelta(hours=1)))
    assert [t.trajectory_id for t in store.query()] == ["early", "mid", "late"]
    assert [t.trajectory_id for t in store.query(limit=2)] == ["early", "mid"]


def test_count_matches_query() -> None:
    store = _DictStore()
    store.save(_trajectory("t1", domain="invoice", success=True))
    store.save(_trajectory("t2", domain="invoice", success=False))
    store.save(_trajectory("t3", domain="ticket", success=True))
    assert store.count(domain="invoice") == len(store.query(domain="invoice"))
    assert store.count(domain="invoice", success=True) == 1
