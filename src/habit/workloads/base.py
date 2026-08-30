# Workload harness: tasks, mock tools, ground-truth checkers, and generator protocol.

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class WorkloadTask:
    task_id: str
    task_input: dict[str, Any]
    expected: dict[str, Any]


@dataclass(frozen=True)
class MockTool:
    name: str
    fn: Callable[..., Any]

    def __call__(self, **kwargs: Any) -> Any:
        return self.fn(**kwargs)


GroundTruthChecker = Callable[[WorkloadTask, dict[str, Any]], bool]


class WorkloadGenerator(Protocol):
    @property
    def domain(self) -> str: ...

    def generate(self, n: int, *, seed: int) -> list[WorkloadTask]: ...

    def tools(self) -> list[MockTool]: ...

    def checker(self) -> GroundTruthChecker: ...
