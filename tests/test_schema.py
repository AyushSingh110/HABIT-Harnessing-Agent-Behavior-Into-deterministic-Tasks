from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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

T0 = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 7, 19, 12, 0, 1, tzinfo=timezone.utc)


def _trajectory() -> Trajectory:
    result = {"total": 42, "lines": [{"sku": "A"}]}
    tool_step = Step(
        step_index=0,
        step_type=StepType.TOOL_CALL,
        llm_call=None,
        tool_call=ToolCall(
            tool_name="fetch_invoice",
            call_id="c1",
            arguments={"id": "INV-1"},
            result=result,
            error=None,
        ),
        tool_result_schema_fingerprint=schema_fingerprint(result),
        context_available=["doc1"],
        context_reads=["doc1"],
        started_at=T0,
        ended_at=T1,
    )
    llm_step = Step(
        step_index=1,
        step_type=StepType.LLM_CALL,
        llm_call=LLMCall(
            provider="groq", model="llama-3.3", input_tokens=100, output_tokens=20
        ),
        tool_call=None,
        tool_result_schema_fingerprint=None,
        context_available=["doc1", "res1"],
        context_reads=["res1"],
        started_at=T0,
        ended_at=T1,
    )
    return Trajectory(
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
        task_input={"id": "INV-1"},
        context_items=[
            ContextItem(
                item_id="doc1",
                kind=ContextKind.DOCUMENT,
                produced_by_step=None,
                content_hash="h1",
                size_tokens=10,
            ),
            ContextItem(
                item_id="res1",
                kind=ContextKind.TOOL_RESULT,
                produced_by_step=0,
                content_hash="h2",
                size_tokens=5,
            ),
        ],
        steps=[tool_step, llm_step],
        outcome=Outcome(
            success=True,
            final_output={"total": 42},
            error=None,
            ground_truth_match=None,
        ),
        started_at=T0,
        ended_at=T1,
        metadata={"framework": "langgraph", "seed": 7},
    )


def test_json_round_trip() -> None:
    traj = _trajectory()
    assert Trajectory.model_validate(traj.model_dump(mode="json")) == traj


def test_dict_round_trip() -> None:
    traj = _trajectory()
    assert Trajectory.model_validate(traj.model_dump()) == traj


def test_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        LLMCall(provider="groq", model="m", input_tokens=1, output_tokens=1, extra="no")  # type: ignore[call-arg]


def test_wrong_type() -> None:
    with pytest.raises(ValidationError):
        LLMCall(provider="groq", model="m", input_tokens="five", output_tokens=1)  # type: ignore[arg-type]


def test_step_invariant_tool_missing() -> None:
    with pytest.raises(ValidationError):
        Step(
            step_index=0,
            step_type=StepType.TOOL_CALL,
            llm_call=None,
            tool_call=None,
            tool_result_schema_fingerprint=None,
            context_available=[],
            context_reads=[],
            started_at=T0,
            ended_at=T1,
        )


def test_step_invariant_llm_with_tool() -> None:
    with pytest.raises(ValidationError):
        Step(
            step_index=0,
            step_type=StepType.LLM_CALL,
            llm_call=LLMCall(
                provider="groq", model="m", input_tokens=1, output_tokens=1
            ),
            tool_call=ToolCall(
                tool_name="t", call_id=None, arguments={}, result=None, error=None
            ),
            tool_result_schema_fingerprint=None,
            context_available=[],
            context_reads=[],
            started_at=T0,
            ended_at=T1,
        )


def test_fingerprint_invariant() -> None:
    with pytest.raises(ValidationError):
        Step(
            step_index=0,
            step_type=StepType.TOOL_CALL,
            llm_call=None,
            tool_call=ToolCall(
                tool_name="t", call_id=None, arguments={}, result={"x": 1}, error=None
            ),
            tool_result_schema_fingerprint=None,
            context_available=[],
            context_reads=[],
            started_at=T0,
            ended_at=T1,
        )


def test_referential_integrity_unknown_id() -> None:
    traj = _trajectory()
    data = traj.model_dump()
    data["steps"][1]["context_reads"] = ["ghost"]
    data["steps"][1]["context_available"] = ["ghost"]
    with pytest.raises(ValidationError):
        Trajectory.model_validate(data)


def test_reads_not_subset() -> None:
    with pytest.raises(ValidationError):
        Step(
            step_index=0,
            step_type=StepType.OTHER,
            llm_call=None,
            tool_call=None,
            tool_result_schema_fingerprint=None,
            context_available=["a"],
            context_reads=["b"],
            started_at=T0,
            ended_at=T1,
        )


def test_naive_datetime_raises() -> None:
    with pytest.raises(ValidationError):
        Step(
            step_index=0,
            step_type=StepType.OTHER,
            llm_call=None,
            tool_call=None,
            tool_result_schema_fingerprint=None,
            context_available=[],
            context_reads=[],
            started_at=datetime(2026, 7, 19, 12, 0, 0),
            ended_at=T1,
        )
