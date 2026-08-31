# Injection study: measure the divergence detector's catch-rate and false-abort rate.

from collections.abc import Callable
from dataclasses import dataclass

from habit.compiler import HabitPlan
from habit.runtime import run_habit_checked
from habit.workloads import MockTool, WorkloadTask


@dataclass(frozen=True)
class DetectionStats:
    normal_runs: int
    false_aborts: int
    shape_runs: int
    shape_caught: int
    value_runs: int
    value_caught: int

    @property
    def false_abort_rate(self) -> float:
        return self.false_aborts / self.normal_runs

    @property
    def shape_catch_rate(self) -> float:
        return self.shape_caught / self.shape_runs

    @property
    def value_catch_rate(self) -> float:
        return self.value_caught / self.value_runs


def run_injection_study(
    plan: HabitPlan,
    expected: list[str | None],
    tasks: list[WorkloadTask],
    tools: dict[str, MockTool],
    *,
    shape_injector: Callable[[dict[str, MockTool]], dict[str, MockTool]],
    value_injector: Callable[[dict[str, MockTool]], dict[str, MockTool]],
) -> DetectionStats:
    shape_tools = shape_injector(tools)
    value_tools = value_injector(tools)

    false_aborts = 0
    shape_caught = 0
    value_caught = 0
    for task in tasks:
        _, normal = run_habit_checked(plan, expected, task.task_input, tools)
        if normal.diverged:
            false_aborts += 1
        _, shape = run_habit_checked(plan, expected, task.task_input, shape_tools)
        if shape.diverged:
            shape_caught += 1
        _, value = run_habit_checked(plan, expected, task.task_input, value_tools)
        if value.diverged:
            value_caught += 1

    n = len(tasks)
    return DetectionStats(
        normal_runs=n,
        false_aborts=false_aborts,
        shape_runs=n,
        shape_caught=shape_caught,
        value_runs=n,
        value_caught=value_caught,
    )
