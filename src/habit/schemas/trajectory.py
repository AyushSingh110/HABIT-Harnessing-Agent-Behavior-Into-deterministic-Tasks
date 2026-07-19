# HABIT trajectory data model: the structured record of one agent run.
# Fields aligned to OpenTelemetry GenAI semantics (see docs/otel_mapping.md).

from enum import Enum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION: str = "1.0.0"


class StepType(str, Enum):
    LLM_CALL = "LLM_CALL"
    TOOL_CALL = "TOOL_CALL"
    OTHER = "OTHER"


class ContextKind(str, Enum):
    DOCUMENT = "DOCUMENT"
    TOOL_RESULT = "TOOL_RESULT"
    MESSAGE = "MESSAGE"
    SYSTEM = "SYSTEM"
    OTHER = "OTHER"


class LLMCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    call_id: str | None
    arguments: dict[str, Any]
    result: Any | None
    error: str | None


class ContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    kind: ContextKind
    produced_by_step: int | None
    content_hash: str | None
    size_tokens: int | None = Field(ge=0, default=None)


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_index: int = Field(ge=0)
    step_type: StepType
    llm_call: LLMCall | None
    tool_call: ToolCall | None
    tool_result_schema_fingerprint: str | None
    context_available: list[str]
    context_reads: list[str]
    started_at: AwareDatetime
    ended_at: AwareDatetime

    @model_validator(mode="after")
    def _check_step_payload(self) -> "Step":
        if self.step_type == StepType.LLM_CALL and not (
            self.llm_call is not None and self.tool_call is None
        ):
            raise ValueError("LLM_CALL step requires llm_call set and tool_call unset")
        if self.step_type == StepType.TOOL_CALL and not (
            self.tool_call is not None and self.llm_call is None
        ):
            raise ValueError("TOOL_CALL step requires tool_call set and llm_call unset")
        if self.step_type == StepType.OTHER and not (
            self.llm_call is None and self.tool_call is None
        ):
            raise ValueError("OTHER step requires both llm_call and tool_call unset")
        return self

    @model_validator(mode="after")
    def _check_fingerprint(self) -> "Step":
        has_result = self.tool_call is not None and self.tool_call.result is not None
        if has_result != (self.tool_result_schema_fingerprint is not None):
            raise ValueError(
                "tool_result_schema_fingerprint must be set iff tool_call.result is set"
            )
        return self

    @model_validator(mode="after")
    def _check_reads_subset(self) -> "Step":
        if not set(self.context_reads) <= set(self.context_available):
            raise ValueError("context_reads must be a subset of context_available")
        return self


class Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    final_output: dict[str, Any]
    error: str | None
    ground_truth_match: bool | None


class Trajectory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    trajectory_id: str
    domain: str
    task_type: str
    task_input: dict[str, Any]
    context_items: list[ContextItem]
    steps: list[Step]
    outcome: Outcome
    started_at: AwareDatetime
    ended_at: AwareDatetime
    metadata: dict[str, Any]

    @model_validator(mode="after")
    def _check_referential_integrity(self) -> "Trajectory":
        known = {item.item_id for item in self.context_items}
        for step in self.steps:
            unknown = (set(step.context_available) | set(step.context_reads)) - known
            if unknown:
                msg = f"unknown item_ids in step {step.step_index}: {sorted(unknown)}"
                raise ValueError(msg)
        return self
