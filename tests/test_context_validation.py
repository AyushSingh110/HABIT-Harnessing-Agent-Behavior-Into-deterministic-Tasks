from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import TrajectoryCluster, cluster_trajectories
from habit.context import (
    ContextPolicy,
    StepContextPolicy,
    induce_and_validate_policy,
    validate_context_policy,
)
from habit.eval import generate_corpus
from habit.schemas import (
    ContextItem,
    ContextKind,
    LLMCall,
    Outcome,
    Step,
    StepType,
    Trajectory,
)
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


def test_invoice_safe(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    validated = induce_and_validate_policy(_cluster_for(trajectories, "invoice"), by_id)
    assert validated.safe is True
    assert validated.validation.checked_steps > 0
    assert validated.validation.starved_steps == 0
    assert validated.validation.starvations == ()


def test_all_domains_safe(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    for domain in ("invoice", "ticket", "report"):
        validated = induce_and_validate_policy(
            _cluster_for(trajectories, domain), by_id
        )
        assert validated.safe is True


def test_held_out_split(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = _cluster_for(trajectories, "invoice")
    validated = induce_and_validate_policy(cluster, by_id, validation_fraction=0.3)
    held_out = sorted(cluster.trajectory_ids)[:3]
    assert len(held_out) == 3
    # 3 held-out invoice trajectories, 9 steps each -> 27 checked.
    assert validated.validation.checked_steps == 27


def _reads_trajectory(trajectory_id: str, item: str) -> Trajectory:
    step = Step(
        step_index=0,
        step_type=StepType.LLM_CALL,
        llm_call=LLMCall(
            provider="fake", model="fake-1", input_tokens=1, output_tokens=1
        ),
        tool_call=None,
        tool_result_schema_fingerprint=None,
        context_available=[item],
        context_reads=[item],
        started_at=T0,
        ended_at=T0,
    )
    return Trajectory(
        trajectory_id=trajectory_id,
        domain="synthetic",
        task_type="t",
        task_input={},
        context_items=[
            ContextItem(
                item_id=item,
                kind=ContextKind.DOCUMENT,
                produced_by_step=None,
                content_hash=None,
                size_tokens=None,
            )
        ],
        steps=[step],
        outcome=Outcome(
            success=True, final_output={}, error=None, ground_truth_match=None
        ),
        started_at=T0,
        ended_at=T0,
        metadata={},
    )


def test_starvation_detected() -> None:
    policy = ContextPolicy(
        signature=(("LLM_CALL", None),),
        steps=[StepContextPolicy(index=0, reads=(), live=(), evictable=())],
    )
    trajectory = _reads_trajectory("t1", "x")
    result = validate_context_policy(policy, [trajectory])
    assert result.safe is False
    assert result.starved_steps == 1
    assert result.starvations == (("t1", 0, ("x",)),)


def test_signature_mismatch_raises() -> None:
    policy = ContextPolicy(
        signature=(("LLM_CALL", None),),
        steps=[StepContextPolicy(index=0, reads=(), live=(), evictable=())],
    )
    two_step = Step(
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
    trajectory = Trajectory(
        trajectory_id="two",
        domain="synthetic",
        task_type="t",
        task_input={},
        context_items=[],
        steps=[two_step, two_step.model_copy(update={"step_index": 1})],
        outcome=Outcome(
            success=True, final_output={}, error=None, ground_truth_match=None
        ),
        started_at=T0,
        ended_at=T0,
        metadata={},
    )
    with pytest.raises(ValueError):
        validate_context_policy(policy, [trajectory])


def test_safe_property_and_determinism(tmp_path: Path) -> None:
    trajectories = _corpus(tmp_path)
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = _cluster_for(trajectories, "invoice")
    a = induce_and_validate_policy(cluster, by_id)
    b = induce_and_validate_policy(cluster, by_id)
    assert a.safe == a.validation.safe
    assert a == b
