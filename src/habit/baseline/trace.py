# Shared context-tracking recorder used by all baseline agents.

from datetime import datetime, timezone
from typing import Any

from habit.baseline.model import LargeModel
from habit.recorder import RunRecorder
from habit.schemas import ContextItem, ContextKind
from habit.workloads import MockTool


class BaselineTrace:
    def __init__(
        self,
        run: RunRecorder,
        model: LargeModel,
        tools: dict[str, MockTool],
        trajectory_id: str,
    ) -> None:
        self._run = run
        self._model = model
        self._tools = tools
        self._trajectory_id = trajectory_id
        self._available: list[str] = []
        self._step = 0

    def add_input(self, item_id: str, kind: ContextKind) -> None:
        self._run.add_context_item(
            ContextItem(
                item_id=item_id,
                kind=kind,
                produced_by_step=None,
                content_hash=None,
                size_tokens=None,
            )
        )
        self._available.append(item_id)

    def llm(self, reads: list[str]) -> None:
        response = self._model.complete(f"step {self._step}")
        now = datetime.now(timezone.utc)
        self._run.record_llm_call(
            provider=self._model.provider,
            model=self._model.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            context_available=list(self._available),
            context_reads=reads,
            started_at=now,
            ended_at=now,
        )
        self._step += 1

    def tool(
        self, name: str, kwargs: dict[str, Any], produced_id: str, reads: list[str]
    ) -> Any:
        result = self._tools[name](**kwargs)
        now = datetime.now(timezone.utc)
        self._run.record_tool_call(
            tool_name=name,
            call_id=f"{self._trajectory_id}-s{self._step}",
            arguments=kwargs,
            result=result,
            error=None,
            context_available=list(self._available),
            context_reads=reads,
            started_at=now,
            ended_at=now,
        )
        self._run.add_context_item(
            ContextItem(
                item_id=produced_id,
                kind=ContextKind.TOOL_RESULT,
                produced_by_step=self._step,
                content_hash=None,
                size_tokens=None,
            )
        )
        self._available.append(produced_id)
        self._step += 1
        return result
