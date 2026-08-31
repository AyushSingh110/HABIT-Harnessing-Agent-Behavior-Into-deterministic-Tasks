# Benchmark: compare the live baseline against the compiled habit on fresh unseen tasks.

import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import create_engine

from habit.baseline import (
    run_invoice_baseline,
    run_report_baseline,
    run_ticket_baseline,
)
from habit.baseline.model import LargeModel
from habit.compiler import HabitPlan, cluster_trajectories, compile_habit, run_habit
from habit.schemas import StepType, Trajectory
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import (
    InvoiceWorkload,
    MockTool,
    ReportWorkload,
    TicketWorkload,
    WorkloadGenerator,
    WorkloadTask,
)

Runner = Callable[..., Trajectory]

_DOMAINS: list[tuple[WorkloadGenerator, Runner]] = [
    (InvoiceWorkload(), run_invoice_baseline),
    (TicketWorkload(), run_ticket_baseline),
    (ReportWorkload(), run_report_baseline),
]

_EVAL_SEED_OFFSET = 10_000


@dataclass(frozen=True)
class SystemMetrics:
    system: str
    tasks: int
    success_rate: float
    mean_llm_calls: float
    mean_tokens: float
    mean_latency_ms: float


@dataclass(frozen=True)
class DomainBenchmark:
    domain: str
    live: SystemMetrics
    habit: SystemMetrics


@dataclass(frozen=True)
class Benchmark:
    per_domain: dict[str, DomainBenchmark]


def _memory_store() -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))


def run_benchmark(
    *,
    model: LargeModel,
    train_per_domain: int = 100,
    eval_per_domain: int = 50,
    seed: int = 0,
) -> Benchmark:
    per_domain: dict[str, DomainBenchmark] = {}
    for workload, runner in _DOMAINS:
        domain = workload.domain
        tools = {tool.name: tool for tool in workload.tools()}

        train_store = _memory_store()
        for i, task in enumerate(workload.generate(train_per_domain, seed=seed)):
            runner(
                task,
                model=model,
                store=train_store,
                tools=tools,
                trajectory_id=f"{domain}-train-{i}",
            )
        trajectories = train_store.query()
        clusters = cluster_trajectories(trajectories)
        by_id = {t.trajectory_id: t for t in trajectories}
        habit = compile_habit(clusters[0], by_id, tools)
        if not habit.usable:
            raise ValueError(f"compiled habit for {domain} did not pass validation")

        eval_tasks = workload.generate(eval_per_domain, seed=seed + _EVAL_SEED_OFFSET)
        live = _live_metrics(eval_tasks, runner, model, tools)
        habit_metrics = _habit_metrics(eval_tasks, habit.plan, workload, tools)
        per_domain[domain] = DomainBenchmark(
            domain=domain, live=live, habit=habit_metrics
        )
    return Benchmark(per_domain=per_domain)


def _live_metrics(
    eval_tasks: list[WorkloadTask],
    runner: Runner,
    model: LargeModel,
    tools: dict[str, MockTool],
) -> SystemMetrics:
    llm_calls: list[int] = []
    tokens: list[int] = []
    successes: list[bool] = []
    latencies: list[float] = []
    for i, task in enumerate(eval_tasks):
        store = _memory_store()
        start = time.perf_counter()
        trajectory = runner(
            task, model=model, store=store, tools=tools, trajectory_id=f"eval-{i}"
        )
        latencies.append((time.perf_counter() - start) * 1000)
        steps = [s for s in trajectory.steps if s.step_type == StepType.LLM_CALL]
        llm_calls.append(len(steps))
        tokens.append(
            sum(
                s.llm_call.input_tokens + s.llm_call.output_tokens
                for s in steps
                if s.llm_call
            )
        )
        successes.append(trajectory.outcome.ground_truth_match is True)
    return _aggregate("live", successes, llm_calls, tokens, latencies)


def _habit_metrics(
    eval_tasks: list[WorkloadTask],
    plan: HabitPlan,
    workload: WorkloadGenerator,
    tools: dict[str, MockTool],
) -> SystemMetrics:
    checker = workload.checker()
    successes: list[bool] = []
    latencies: list[float] = []
    for task in eval_tasks:
        start = time.perf_counter()
        output = run_habit(plan, task.task_input, tools)
        latencies.append((time.perf_counter() - start) * 1000)
        successes.append(checker(task, output))
    n = len(eval_tasks)
    return _aggregate("habit", successes, [0] * n, [0] * n, latencies)


def _aggregate(
    system: str,
    successes: list[bool],
    llm_calls: list[int],
    tokens: list[int],
    latencies: list[float],
) -> SystemMetrics:
    n = len(successes)
    return SystemMetrics(
        system=system,
        tasks=n,
        success_rate=sum(successes) / n,
        mean_llm_calls=sum(llm_calls) / n,
        mean_tokens=sum(tokens) / n,
        mean_latency_ms=sum(latencies) / n,
    )
