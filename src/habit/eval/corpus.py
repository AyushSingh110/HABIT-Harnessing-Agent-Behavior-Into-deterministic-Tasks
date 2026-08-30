# Corpus generation: run the baseline agents over generated tasks and summarize.

from collections.abc import Callable
from dataclasses import dataclass

from habit.baseline import (
    run_invoice_baseline,
    run_report_baseline,
    run_ticket_baseline,
)
from habit.baseline.model import LargeModel
from habit.interfaces import TrajectoryStore
from habit.schemas import Trajectory
from habit.workloads import (
    InvoiceWorkload,
    ReportWorkload,
    TicketWorkload,
    WorkloadGenerator,
)

Runner = Callable[..., Trajectory]

_DOMAINS: list[tuple[WorkloadGenerator, Runner]] = [
    (InvoiceWorkload(), run_invoice_baseline),
    (TicketWorkload(), run_ticket_baseline),
    (ReportWorkload(), run_report_baseline),
]


@dataclass(frozen=True)
class DomainStats:
    domain: str
    count: int
    match_rate: float
    mean_steps: float
    min_steps: int
    max_steps: int


@dataclass(frozen=True)
class CorpusSummary:
    per_domain: dict[str, DomainStats]
    total: int


def generate_corpus(
    store: TrajectoryStore, *, model: LargeModel, per_domain: int, seed: int = 0
) -> CorpusSummary:
    per_domain_stats: dict[str, DomainStats] = {}
    for workload, runner in _DOMAINS:
        domain = workload.domain
        tools = {tool.name: tool for tool in workload.tools()}
        tasks = workload.generate(per_domain, seed=seed)
        trajectories = [
            runner(
                task,
                model=model,
                store=store,
                tools=tools,
                trajectory_id=f"{domain}-{seed}-{i}",
            )
            for i, task in enumerate(tasks)
        ]
        per_domain_stats[domain] = _summarize(domain, trajectories)
    return CorpusSummary(
        per_domain=per_domain_stats,
        total=sum(stats.count for stats in per_domain_stats.values()),
    )


def _summarize(domain: str, trajectories: list[Trajectory]) -> DomainStats:
    step_counts = [len(traj.steps) for traj in trajectories]
    matches = sum(1 for traj in trajectories if traj.outcome.ground_truth_match)
    count = len(trajectories)
    return DomainStats(
        domain=domain,
        count=count,
        match_rate=matches / count,
        mean_steps=sum(step_counts) / count,
        min_steps=min(step_counts),
        max_steps=max(step_counts),
    )
