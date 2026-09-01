# Baseline ladder: HABIT structural reuse vs. exact-match semantic cache vs. vanilla.

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import cluster_trajectories, compile_habit, run_habit
from habit.eval.research import ShiftableWorkload
from habit.runtime import Router, build_router
from habit.schemas import StepType, Trajectory
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import MockTool, WorkloadTask

Runner = Callable[..., Trajectory]


class SemanticCache:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def key(self, task_input: dict[str, Any]) -> str:
        return json.dumps(task_input, sort_keys=True)

    def get(self, task_input: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.get(self.key(task_input))

    def put(self, task_input: dict[str, Any], output: dict[str, Any]) -> None:
        self._store[self.key(task_input)] = output


@dataclass(frozen=True)
class StrategyResult:
    strategy: str
    tasks: int
    reuse_rate: float
    mean_live_llm_calls: float
    success_rate: float


def _memory_store() -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))


def _live_llm_calls(trajectory: Trajectory) -> int:
    return sum(1 for s in trajectory.steps if s.step_type == StepType.LLM_CALL)


def _build_stream(
    workload: ShiftableWorkload, *, n: int, repeat_fraction: float, seed: int
) -> list[WorkloadTask]:
    n_repeat = int(n * repeat_fraction)
    fresh = workload.generate(n - n_repeat, seed=seed)
    stream = list(fresh)
    for i in range(n_repeat):
        stream.append(fresh[i % len(fresh)])
    return stream


def compare_strategies(
    workload: ShiftableWorkload,
    runner: Runner,
    *,
    n: int = 60,
    repeat_fraction: float = 0.3,
    seed: int = 0,
) -> dict[str, StrategyResult]:
    tools = {tool.name: tool for tool in workload.tools()}
    checker = workload.checker()
    stream = _build_stream(workload, n=n, repeat_fraction=repeat_fraction, seed=seed)

    train = workload.generate(40, seed=seed + 1)
    train_store = _memory_store()
    for i, task in enumerate(train):
        runner(
            task,
            model=FakeModel(),
            store=train_store,
            tools=tools,
            trajectory_id=f"train-{i}",
        )
    trajectories = train_store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    compiled = compile_habit(cluster_trajectories(trajectories)[0], by_id, tools)
    router = build_router({workload.domain: compiled})

    return {
        "vanilla": _run_vanilla(runner, checker, tools, stream),
        "cache": _run_cache(runner, checker, tools, stream),
        "habit": _run_habit(workload.domain, router, checker, tools, stream),
    }


def _run_vanilla(
    runner: Runner,
    checker: Callable[[WorkloadTask, dict[str, Any]], bool],
    tools: dict[str, MockTool],
    stream: list[WorkloadTask],
) -> StrategyResult:
    store = _memory_store()
    calls = 0
    successes = 0
    for i, task in enumerate(stream):
        traj = runner(
            task, model=FakeModel(), store=store, tools=tools, trajectory_id=f"v-{i}"
        )
        calls += _live_llm_calls(traj)
        successes += checker(task, traj.outcome.final_output)
    n = len(stream)
    return StrategyResult("vanilla", n, 0.0, calls / n, successes / n)


def _run_cache(
    runner: Runner,
    checker: Callable[[WorkloadTask, dict[str, Any]], bool],
    tools: dict[str, MockTool],
    stream: list[WorkloadTask],
) -> StrategyResult:
    store = _memory_store()
    cache = SemanticCache()
    calls = 0
    reused = 0
    successes = 0
    for i, task in enumerate(stream):
        hit = cache.get(task.task_input)
        if hit is not None:
            reused += 1
            output = hit
        else:
            traj = runner(
                task,
                model=FakeModel(),
                store=store,
                tools=tools,
                trajectory_id=f"c-{i}",
            )
            calls += _live_llm_calls(traj)
            output = traj.outcome.final_output
            cache.put(task.task_input, output)
        successes += checker(task, output)
    n = len(stream)
    return StrategyResult("cache", n, reused / n, calls / n, successes / n)


def _run_habit(
    domain: str,
    router: Router,
    checker: Callable[[WorkloadTask, dict[str, Any]], bool],
    tools: dict[str, MockTool],
    stream: list[WorkloadTask],
) -> StrategyResult:
    reused = 0
    successes = 0
    for task in stream:
        plan = router.route(domain, task.task_input)
        if plan is None:
            continue
        reused += 1
        successes += checker(task, run_habit(plan, task.task_input, tools))
    n = len(stream)
    return StrategyResult("habit", n, reused / n, 0.0, successes / n)
