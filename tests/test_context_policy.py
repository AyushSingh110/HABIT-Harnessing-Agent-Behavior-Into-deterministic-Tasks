from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import TrajectoryCluster, cluster_trajectories, structural_signature
from habit.context import induce_context_policy, working_set_sizes
from habit.eval import generate_corpus
from habit.schemas import LLMCall, Outcome, Step, StepType, ToolCall, Trajectory
from habit.storage import SqlAlchemyTrajectoryStore

T0 = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def _corpus(tmp_path: Path) -> list[Trajectory]:
    store = SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )
    generate_corpus(store, model=FakeModel(), per_domain=10, seed=1)
    return store.query()


def _cluster_for(trajectories: list[Trajectory], domain: str) -> TrajectoryCluster:
    by_id = {t.trajectory_id: t for t in trajectories}
    for cluster in cluster_trajectories(trajectories):
        if by_id[cluster.trajectory_ids[0]].domain == domain:
            return cluster
    raise AssertionError(domain)


def test_invoice_shape_and_reads(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    policy = induce_context_policy(_cluster_for(trajectories, "invoice"), by_id)
    assert len(policy.steps) == 9
    assert policy.steps[7].reads == ("header",)


def test_eviction_and_liveness(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    policy = induce_context_policy(_cluster_for(trajectories, "invoice"), by_id)
    assert "invoice" in policy.steps[6].evictable
    assert "invoice" not in policy.steps[6].live
    # line_items is produced at step 3, so it is available from step 4; read at step 8,
    # it stays live across 4..8 and is never evictable before that final read.
    for k in range(4, 9):
        assert "line_items" in policy.steps[k].live
        assert "line_items" not in policy.steps[k].evictable


def test_invariants(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    for domain in ("invoice", "ticket", "report"):
        policy = induce_context_policy(_cluster_for(trajectories, domain), by_id)
        for step in policy.steps:
            assert set(step.reads) <= set(step.live)
            assert set(step.live).isdisjoint(step.evictable)


def test_working_set_sizes(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    policy = induce_context_policy(_cluster_for(trajectories, "invoice"), by_id)
    peak_naive, peak_policy = working_set_sizes(policy)
    assert peak_policy <= peak_naive
    assert peak_policy < peak_naive


def test_all_domains_and_determinism(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    expected_steps = {"invoice": 9, "ticket": 11, "report": 11}
    for domain, count in expected_steps.items():
        cluster = _cluster_for(trajectories, domain)
        policy = induce_context_policy(cluster, by_id)
        assert len(policy.steps) == count
        assert policy == induce_context_policy(cluster, by_id)


def _tool_trajectory(trajectory_id: str) -> Trajectory:
    step = Step(
        step_index=0,
        step_type=StepType.TOOL_CALL,
        llm_call=None,
        tool_call=ToolCall(
            tool_name="t", call_id=None, arguments={}, result={"a": 1}, error=None
        ),
        tool_result_schema_fingerprint="deadbeefdeadbeef",
        context_available=[],
        context_reads=[],
        started_at=T0,
        ended_at=T0,
    )
    return _wrap(trajectory_id, [step])


def _llm_trajectory(trajectory_id: str) -> Trajectory:
    step = Step(
        step_index=0,
        step_type=StepType.LLM_CALL,
        llm_call=LLMCall(
            provider="fake", model="fake-1", input_tokens=1, output_tokens=1
        ),
        tool_call=None,
        tool_result_schema_fingerprint=None,
        context_available=[],
        context_reads=[],
        started_at=T0,
        ended_at=T0,
    )
    return _wrap(trajectory_id, [step])


def _wrap(trajectory_id: str, steps: list[Step]) -> Trajectory:
    return Trajectory(
        trajectory_id=trajectory_id,
        domain="synthetic",
        task_type="t",
        task_input={},
        context_items=[],
        steps=steps,
        outcome=Outcome(
            success=True, final_output={}, error=None, ground_truth_match=None
        ),
        started_at=T0,
        ended_at=T0,
        metadata={},
    )


def test_divergent_and_missing_raise() -> None:
    a = _tool_trajectory("a")
    b = _llm_trajectory("b")
    cluster = TrajectoryCluster(
        signature=structural_signature(a), trajectory_ids=["a", "b"]
    )
    with pytest.raises(ValueError):
        induce_context_policy(cluster, {"a": a, "b": b})

    missing = TrajectoryCluster(
        signature=structural_signature(a), trajectory_ids=["a", "ghost"]
    )
    with pytest.raises(ValueError):
        induce_context_policy(missing, {"a": a})
