# LangGraph/LangChain adapter: records a run's LLM and tool events as a Trajectory.

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.runnables import Runnable

from habit.interfaces import TrajectoryStore
from habit.recorder import RunRecorder, TrajectoryRecorder
from habit.schemas import Trajectory


def _usage(response: LLMResult) -> tuple[int, int]:
    for generations in response.generations:
        for generation in generations:
            usage = getattr(
                getattr(generation, "message", None), "usage_metadata", None
            )
            if usage:
                return int(usage.get("input_tokens", 0)), int(
                    usage.get("output_tokens", 0)
                )
    return 0, 0


# Maps LangChain callback events to recorder calls. Context capture is out of scope.
class HabitCallbackHandler(BaseCallbackHandler):
    def __init__(self, run: RunRecorder) -> None:
        self._run = run
        self._llm_starts: dict[UUID, tuple[str, str, datetime]] = {}
        self._tool_starts: dict[UUID, tuple[str, dict[str, Any], datetime]] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        meta = metadata or {}
        provider = meta.get("ls_provider", "unknown")
        model = meta.get("ls_model_name") or serialized.get("name") or "unknown"
        self._llm_starts[run_id] = (provider, model, datetime.now(timezone.utc))

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        provider, model, started_at = self._llm_starts.pop(run_id)
        input_tokens, output_tokens = _usage(response)
        self._run.record_llm_call(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            context_available=[],
            context_reads=[],
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        arguments = inputs if inputs is not None else {"input": input_str}
        self._tool_starts[run_id] = (tool_name, arguments, datetime.now(timezone.utc))

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        tool_name, arguments, started_at = self._tool_starts.pop(run_id)
        self._run.record_tool_call(
            tool_name=tool_name,
            call_id=str(run_id),
            arguments=arguments,
            result=output,
            error=None,
            context_available=[],
            context_reads=[],
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
        )


def record_langgraph_run(
    app: Runnable[Any, Any],
    task_input: dict[str, Any],
    *,
    store: TrajectoryStore,
    trajectory_id: str,
    domain: str,
    task_type: str,
    metadata: dict[str, Any] | None = None,
    final_output_key: str | None = None,
) -> Trajectory:
    run = TrajectoryRecorder(store).start_run(
        trajectory_id=trajectory_id,
        domain=domain,
        task_type=task_type,
        task_input=task_input,
        metadata=metadata or {},
        started_at=datetime.now(timezone.utc),
    )
    handler = HabitCallbackHandler(run)
    try:
        result = app.invoke(task_input, config={"callbacks": [handler]})
    except Exception as exc:
        run.finish(
            success=False,
            final_output={},
            ended_at=datetime.now(timezone.utc),
            error=str(exc),
        )
        raise

    final_output = result[final_output_key] if final_output_key is not None else result
    return run.finish(
        success=True,
        final_output=dict(final_output),
        ended_at=datetime.now(timezone.utc),
    )
