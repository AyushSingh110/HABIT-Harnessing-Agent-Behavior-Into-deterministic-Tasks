from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import (
    TrajectoryCluster,
    cluster_trajectories,
    induce_skeleton,
    structural_signature,
)
from habit.eval import generate_corpus
from habit.schemas import (
    LLMCall,
    Outcome,
    Step,
    StepType,
    ToolCall,
    Trajectory,
    schema_fingerprint,
)
from habit.storage import SqlAlchemyTrajectoryStore

T0 = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def skeletons_by_domain(tmp_path: Path) -> dict[str, Any]:
    store = SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )
    generate_corpus(store, model=FakeModel(), per_domain=5, seed=1)
    trajectories = store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    result = {}
    for cluster in cluster_trajectories(trajectories):
        domain = by_id[cluster.trajectory_ids[0]].domain
        result[domain] = induce_skeleton(cluster, by_id)
    return result


def test_invoice_skeleton(skeletons_by_domain: dict[str, Any]) -> None:
    skeleton = skeletons_by_domain["invoice"]
    kinds = [s.step_type for s in skeleton.steps]
    assert kinds == [
        "LLM_CALL",
        "TOOL_CALL",
        "LLM_CALL",
        "TOOL_CALL",
        "LLM_CALL",
        "TOOL_CALL",
        "LLM_CALL",
        "TOOL_CALL",
        "LLM_CALL",
    ]
    for step in skeleton.steps:
        if step.step_type == "TOOL_CALL":
            assert step.stable is True
            assert step.result_fingerprint is not None
        else:
            assert step.stable is False


def test_invoice_vendor_step(skeletons_by_domain: dict[str, Any]) -> None:
    skeleton = skeletons_by_domain["invoice"]
    vendor_step = next(s for s in skeleton.steps if s.tool_name == "lookup_vendor")
    assert vendor_step.context_reads == ("header",)
    assert skeleton.support == 5


def test_ticket_skeleton(skeletons_by_domain: dict[str, Any]) -> None:
    skeleton = skeletons_by_domain["ticket"]
    assert len(skeleton.steps) == 11
    for step in skeleton.steps:
        if step.step_type == "TOOL_CALL":
            assert step.stable is True
        else:
            assert step.stable is False


def test_report_skeleton(skeletons_by_domain: dict[str, Any]) -> None:
    skeleton = skeletons_by_domain["report"]
    assert len(skeleton.steps) == 11
    for step in skeleton.steps:
        if step.step_type == "LLM_CALL":
            assert step.stable is False
        elif step.tool_name == "aggregate":
            # aggregate's result includes a variable-key "totals" dict, so its
            # result-shape fingerprint differs across the cluster -> not stable.
            assert step.stable is False
            assert step.result_fingerprint is None
        else:
            assert step.stable is True


def _tool_trajectory(trajectory_id: str, result: dict[str, Any]) -> Trajectory:
    step = Step(
        step_index=0,
        step_type=StepType.TOOL_CALL,
        llm_call=None,
        tool_call=ToolCall(
            tool_name="t", call_id=None, arguments={}, result=result, error=None
        ),
        tool_result_schema_fingerprint=schema_fingerprint(result),
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


def test_unstable_fingerprint() -> None:
    a = _tool_trajectory("a", {"a": 1})
    b = _tool_trajectory("b", {"a": 1, "b": 2})
    cluster = TrajectoryCluster(
        signature=structural_signature(a), trajectory_ids=["a", "b"]
    )
    skeleton = induce_skeleton(cluster, {"a": a, "b": b})
    assert skeleton.steps[0].result_fingerprint is None
    assert skeleton.steps[0].stable is False


def test_divergent_and_missing_raise() -> None:
    a = _tool_trajectory("a", {"a": 1})
    b = _llm_trajectory("b")
    cluster = TrajectoryCluster(
        signature=structural_signature(a), trajectory_ids=["a", "b"]
    )
    with pytest.raises(ValueError):
        induce_skeleton(cluster, {"a": a, "b": b})

    missing = TrajectoryCluster(
        signature=structural_signature(a), trajectory_ids=["a", "ghost"]
    )
    with pytest.raises(ValueError):
        induce_skeleton(missing, {"a": a})
