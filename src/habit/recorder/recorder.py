# Framework-agnostic Flight Recorder: assembles validated Trajectories and persists them

from datetime import datetime, timezone
from typing import Any

from habit.interfaces import TrajectoryStore
from habit.schemas import (
    ContextItem,
    LLMCall,
    Outcome,
    Step,
    StepType,
    ToolCall,
    Trajectory,
    schema_fingerprint,
)


def _to_utc(dt: datetime) -> datetime:
    # Aware datetimes normalize to UTC; naive ones pass through for the schema to reject
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc)


class TrajectoryRecorder:
    def __init__(self, store: TrajectoryStore) -> None:
        self._store = store

    def start_run(
        self,
        *,
        trajectory_id: str,
        domain: str,
        task_type: str,
        task_input: dict[str, Any],
        metadata: dict[str, Any],
        started_at: datetime,
    ) -> "RunRecorder":
        return RunRecorder(
            store=self._store,
            trajectory_id=trajectory_id,
            domain=domain,
            task_type=task_type,
            task_input=task_input,
            metadata=metadata,
            started_at=_to_utc(started_at),
        )


class RunRecorder:
    def __init__(
        self,
        *,
        store: TrajectoryStore,
        trajectory_id: str,
        domain: str,
        task_type: str,
        task_input: dict[str, Any],
        metadata: dict[str, Any],
        started_at: datetime,
    ) -> None:
        self._store = store
        self._trajectory_id = trajectory_id
        self._domain = domain
        self._task_type = task_type
        self._task_input = task_input
        self._metadata = metadata
        self._started_at = started_at
        self._context_items: list[ContextItem] = []
        self._steps: list[Step] = []

    def add_context_item(self, item: ContextItem) -> None:
        self._context_items.append(item)

    def record_llm_call(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        context_available: list[str],
        context_reads: list[str],
        started_at: datetime,
        ended_at: datetime,
    ) -> None:
        self._append_step(
            step_type=StepType.LLM_CALL,
            llm_call=LLMCall(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            tool_call=None,
            tool_result_schema_fingerprint=None,
            context_available=context_available,
            context_reads=context_reads,
            started_at=started_at,
            ended_at=ended_at,
        )

    def record_tool_call(
        self,
        *,
        tool_name: str,
        call_id: str | None,
        arguments: dict[str, Any],
        result: Any | None,
        error: str | None,
        context_available: list[str],
        context_reads: list[str],
        started_at: datetime,
        ended_at: datetime,
    ) -> None:
        fingerprint = schema_fingerprint(result) if result is not None else None
        self._append_step(
            step_type=StepType.TOOL_CALL,
            llm_call=None,
            tool_call=ToolCall(
                tool_name=tool_name,
                call_id=call_id,
                arguments=arguments,
                result=result,
                error=error,
            ),
            tool_result_schema_fingerprint=fingerprint,
            context_available=context_available,
            context_reads=context_reads,
            started_at=started_at,
            ended_at=ended_at,
        )

    def record_other(
        self,
        *,
        context_available: list[str],
        context_reads: list[str],
        started_at: datetime,
        ended_at: datetime,
    ) -> None:
        self._append_step(
            step_type=StepType.OTHER,
            llm_call=None,
            tool_call=None,
            tool_result_schema_fingerprint=None,
            context_available=context_available,
            context_reads=context_reads,
            started_at=started_at,
            ended_at=ended_at,
        )

    def finish(
        self,
        *,
        success: bool,
        final_output: dict[str, Any],
        ended_at: datetime,
        error: str | None = None,
        ground_truth_match: bool | None = None,
    ) -> Trajectory:
        trajectory = Trajectory(
            trajectory_id=self._trajectory_id,
            domain=self._domain,
            task_type=self._task_type,
            task_input=self._task_input,
            context_items=self._context_items,
            steps=self._steps,
            outcome=Outcome(
                success=success,
                final_output=final_output,
                error=error,
                ground_truth_match=ground_truth_match,
            ),
            started_at=self._started_at,
            ended_at=_to_utc(ended_at),
            metadata=self._metadata,
        )
        self._store.save(trajectory)
        return trajectory

    def _append_step(
        self,
        *,
        step_type: StepType,
        llm_call: LLMCall | None,
        tool_call: ToolCall | None,
        tool_result_schema_fingerprint: str | None,
        context_available: list[str],
        context_reads: list[str],
        started_at: datetime,
        ended_at: datetime,
    ) -> None:
        self._steps.append(
            Step(
                step_index=len(self._steps),
                step_type=step_type,
                llm_call=llm_call,
                tool_call=tool_call,
                tool_result_schema_fingerprint=tool_result_schema_fingerprint,
                context_available=context_available,
                context_reads=context_reads,
                started_at=_to_utc(started_at),
                ended_at=_to_utc(ended_at),
            )
        )
