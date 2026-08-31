# Context policy induction: per-step liveness analysis over recorded access patterns.

from dataclasses import dataclass

from habit.compiler import TrajectoryCluster, structural_signature
from habit.compiler.clustering import Signature
from habit.schemas import Trajectory


@dataclass(frozen=True)
class StepContextPolicy:
    index: int
    reads: tuple[str, ...]
    live: tuple[str, ...]
    evictable: tuple[str, ...]


@dataclass(frozen=True)
class ContextPolicy:
    signature: Signature
    steps: list[StepContextPolicy]


def induce_context_policy(
    cluster: TrajectoryCluster, trajectories_by_id: dict[str, Trajectory]
) -> ContextPolicy:
    trajectories: list[Trajectory] = []
    for trajectory_id in cluster.trajectory_ids:
        trajectory = trajectories_by_id.get(trajectory_id)
        if trajectory is None:
            raise ValueError(
                f"trajectory_id not in trajectories_by_id: {trajectory_id}"
            )
        if structural_signature(trajectory) != cluster.signature:
            raise ValueError(
                f"trajectory diverges from cluster signature: {trajectory_id}"
            )
        trajectories.append(trajectory)

    n = len(cluster.signature)
    reads_per_step: list[set[str]] = [set() for _ in range(n)]
    available_per_step: list[set[str]] = [set() for _ in range(n)]
    for trajectory in trajectories:
        for i, step in enumerate(trajectory.steps):
            reads_per_step[i].update(step.context_reads)
            available_per_step[i].update(step.context_available)

    last_read: dict[str, int] = {}
    for i, reads in enumerate(reads_per_step):
        for item in reads:
            last_read[item] = i

    steps: list[StepContextPolicy] = []
    for i in range(n):
        live = {
            item
            for item in available_per_step[i]
            if item in last_read and last_read[item] >= i
        }
        evictable = available_per_step[i] - live
        steps.append(
            StepContextPolicy(
                index=i,
                reads=tuple(sorted(reads_per_step[i])),
                live=tuple(sorted(live)),
                evictable=tuple(sorted(evictable)),
            )
        )
    return ContextPolicy(signature=cluster.signature, steps=steps)


def working_set_sizes(policy: ContextPolicy) -> tuple[int, int]:
    if not policy.steps:
        return (0, 0)
    peak_naive = max(len(step.live) + len(step.evictable) for step in policy.steps)
    peak_policy = max(len(step.live) for step in policy.steps)
    return (peak_naive, peak_policy)
