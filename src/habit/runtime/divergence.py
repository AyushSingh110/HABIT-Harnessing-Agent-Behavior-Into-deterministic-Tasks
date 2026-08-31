# Divergence detector: run a habit under monitoring and flag off-script tool results.

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from habit.compiler import HabitPlan, Skeleton, run_habit
from habit.schemas import schema_fingerprint
from habit.workloads import MockTool


@dataclass(frozen=True)
class DivergenceReport:
    diverged: bool
    step_ordinal: int | None
    tool_name: str | None
    expected_fingerprint: str | None
    actual_fingerprint: str | None


def expected_tool_fingerprints(skeleton: Skeleton) -> list[str | None]:
    return [
        step.result_fingerprint
        for step in skeleton.steps
        if step.step_type == "TOOL_CALL"
    ]


def _recording_tool(real: MockTool, recorded: list[Any]) -> Callable[..., Any]:
    def fn(**kwargs: Any) -> Any:
        result = real(**kwargs)
        recorded.append(result)
        return result

    return fn


def run_habit_checked(
    plan: HabitPlan,
    expected: list[str | None],
    task_input: dict[str, Any],
    tools: dict[str, MockTool],
) -> tuple[dict[str, Any] | None, DivergenceReport]:
    recorded: list[Any] = []
    wrapped = {
        name: MockTool(name=name, fn=_recording_tool(tool, recorded))
        for name, tool in tools.items()
    }

    # A habit that fails to execute is itself a divergence signal, not an error.
    failed = False
    output: dict[str, Any] | None = None
    try:
        output = run_habit(plan, task_input, wrapped)
    except Exception:
        failed = True

    for k, result in enumerate(recorded):
        if k < len(expected) and expected[k] is not None:
            actual = schema_fingerprint(result)
            if actual != expected[k]:
                return None, DivergenceReport(
                    diverged=True,
                    step_ordinal=k,
                    tool_name=plan.steps[k].tool_name,
                    expected_fingerprint=expected[k],
                    actual_fingerprint=actual,
                )

    if failed:
        ordinal = len(recorded)
        tool_name = plan.steps[ordinal].tool_name if ordinal < len(plan.steps) else None
        return None, DivergenceReport(
            diverged=True,
            step_ordinal=ordinal,
            tool_name=tool_name,
            expected_fingerprint=None,
            actual_fingerprint=None,
        )

    return output, DivergenceReport(
        diverged=False,
        step_ordinal=None,
        tool_name=None,
        expected_fingerprint=None,
        actual_fingerprint=None,
    )
