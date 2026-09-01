# Research experiments: habit generalization and policy safety under distribution shift.

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import cluster_trajectories, compile_habit, run_habit
from habit.context import induce_and_validate_policy, validate_context_policy
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import GroundTruthChecker, MockTool, WorkloadTask

Runner = Callable[..., Trajectory]


# A workload that also exposes the distribution-shifted split (shifted=True).
class ShiftableWorkload(Protocol):
    @property
    def domain(self) -> str: ...

    def generate(
        self, n: int, *, seed: int, shifted: bool = False
    ) -> list[WorkloadTask]: ...

    def tools(self) -> list[MockTool]: ...

    def checker(self) -> GroundTruthChecker: ...


@dataclass(frozen=True)
class GeneralizationResult:
    domain: str
    normal_success: float
    shifted_success: float


@dataclass(frozen=True)
class SafetyUnderShiftResult:
    domain: str
    normal_safe: bool
    shifted_safe: bool
    shifted_starvations: int


def _memory_store() -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))


def _record(
    workload: ShiftableWorkload,
    runner: Runner,
    tools: dict[str, MockTool],
    *,
    n: int,
    seed: int,
    shifted: bool,
    tag: str,
) -> list[Trajectory]:
    store = _memory_store()
    for i, task in enumerate(workload.generate(n, seed=seed, shifted=shifted)):
        runner(
            task,
            model=FakeModel(),
            store=store,
            tools=tools,
            trajectory_id=f"{tag}-{i}",
        )
    return store.query()


def generalization_gap(
    workload: ShiftableWorkload,
    runner: Runner,
    *,
    train_n: int = 40,
    eval_n: int = 40,
    seed: int = 0,
) -> GeneralizationResult:
    tools = {tool.name: tool for tool in workload.tools()}
    checker = workload.checker()
    trajectories = _record(
        workload, runner, tools, n=train_n, seed=seed, shifted=False, tag="train"
    )
    by_id = {t.trajectory_id: t for t in trajectories}
    plan = compile_habit(cluster_trajectories(trajectories)[0], by_id, tools).plan

    normal_tasks = workload.generate(eval_n, seed=seed + 1)
    shifted_tasks = workload.generate(eval_n, seed=seed + 1, shifted=True)
    normal = sum(
        checker(task, run_habit(plan, task.task_input, tools)) for task in normal_tasks
    )
    shifted = sum(
        checker(task, run_habit(plan, task.task_input, tools)) for task in shifted_tasks
    )
    return GeneralizationResult(
        domain=workload.domain,
        normal_success=normal / eval_n,
        shifted_success=shifted / eval_n,
    )


def safety_under_shift(
    workload: ShiftableWorkload,
    runner: Runner,
    *,
    train_n: int = 40,
    eval_n: int = 40,
    seed: int = 0,
) -> SafetyUnderShiftResult:
    tools = {tool.name: tool for tool in workload.tools()}
    normal_trajectories = _record(
        workload, runner, tools, n=train_n, seed=seed, shifted=False, tag="normal"
    )
    normal_by_id = {t.trajectory_id: t for t in normal_trajectories}
    validated = induce_and_validate_policy(
        cluster_trajectories(normal_trajectories)[0], normal_by_id
    )

    shifted_trajectories = _record(
        workload, runner, tools, n=eval_n, seed=seed + 1, shifted=True, tag="shifted"
    )
    shifted_validation = validate_context_policy(validated.policy, shifted_trajectories)
    return SafetyUnderShiftResult(
        domain=workload.domain,
        normal_safe=validated.safe,
        shifted_safe=shifted_validation.safe,
        shifted_starvations=shifted_validation.starved_steps,
    )
