# Reliability study: live-agent success (~r^N) vs. the deterministic habit.

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import create_engine

from habit.baseline import FakeModel, ModelFailure, UnreliableModel
from habit.compiler import cluster_trajectories, compile_habit, run_habit
from habit.eval.research import ShiftableWorkload
from habit.schemas import StepType, Trajectory
from habit.storage import SqlAlchemyTrajectoryStore

Runner = Callable[..., Trajectory]


@dataclass(frozen=True)
class ReliabilityResult:
    domain: str
    reliability: float
    llm_calls: int
    live_success_rate: float
    habit_success_rate: float


def _memory_store() -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))


def reliability_study(
    workload: ShiftableWorkload,
    runner: Runner,
    *,
    reliabilities: tuple[float, ...] = (0.8, 0.9, 0.95, 0.99, 1.0),
    n_tasks: int = 100,
    seed: int = 0,
) -> list[ReliabilityResult]:
    tools = {tool.name: tool for tool in workload.tools()}
    checker = workload.checker()

    train_store = _memory_store()
    for i, task in enumerate(workload.generate(40, seed=seed)):
        runner(
            task,
            model=FakeModel(),
            store=train_store,
            tools=tools,
            trajectory_id=f"train-{i}",
        )
    trajectories = train_store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    plan = compile_habit(cluster_trajectories(trajectories)[0], by_id, tools).plan
    llm_calls = sum(
        1 for s in trajectories[0].steps if s.step_type == StepType.LLM_CALL
    )

    eval_tasks = workload.generate(n_tasks, seed=seed + 1)
    results: list[ReliabilityResult] = []
    for reliability in reliabilities:
        model = UnreliableModel(reliability=reliability, seed=seed)
        live_ok = 0
        for i, task in enumerate(eval_tasks):
            try:
                traj = runner(
                    task,
                    model=model,
                    store=_memory_store(),
                    tools=tools,
                    trajectory_id=f"live-{i}",
                )
            except ModelFailure:
                continue
            if traj.outcome.ground_truth_match is True:
                live_ok += 1
        habit_ok = sum(
            checker(task, run_habit(plan, task.task_input, tools))
            for task in eval_tasks
        )
        results.append(
            ReliabilityResult(
                domain=workload.domain,
                reliability=reliability,
                llm_calls=llm_calls,
                live_success_rate=live_ok / n_tasks,
                habit_success_rate=habit_ok / n_tasks,
            )
        )
    return results
