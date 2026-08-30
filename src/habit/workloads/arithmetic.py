# Minimal example domain that exercises the workload harness end to end.

import random
from typing import Any

from habit.workloads.base import (
    GroundTruthChecker,
    MockTool,
    WorkloadTask,
)

_NUMBERS_PER_TASK = 4
_INT_RANGE = (1, 100)


def _add(numbers: list[int]) -> dict[str, Any]:
    return {"result": sum(numbers)}


def _check(task: WorkloadTask, final_output: dict[str, Any]) -> bool:
    return bool(final_output.get("result") == task.expected["result"])


class ArithmeticWorkload:
    @property
    def domain(self) -> str:
        return "arithmetic"

    def generate(self, n: int, *, seed: int) -> list[WorkloadTask]:
        rng = random.Random(seed)
        tasks: list[WorkloadTask] = []
        for i in range(n):
            numbers = [rng.randint(*_INT_RANGE) for _ in range(_NUMBERS_PER_TASK)]
            tasks.append(
                WorkloadTask(
                    task_id=f"arithmetic-{seed}-{i}",
                    task_input={"numbers": numbers},
                    expected={"result": sum(numbers)},
                )
            )
        return tasks

    def tools(self) -> list[MockTool]:
        return [MockTool(name="add", fn=_add)]

    def checker(self) -> GroundTruthChecker:
        return _check
