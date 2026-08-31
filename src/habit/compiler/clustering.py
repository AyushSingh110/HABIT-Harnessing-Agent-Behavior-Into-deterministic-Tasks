# Structural clustering: group trajectories by their exact ordered step signature.

from collections import defaultdict
from dataclasses import dataclass

from habit.schemas import Trajectory

Signature = tuple[tuple[str, str | None], ...]


def structural_signature(trajectory: Trajectory) -> Signature:
    return tuple(
        (step.step_type.value, step.tool_call.tool_name if step.tool_call else None)
        for step in trajectory.steps
    )


@dataclass(frozen=True)
class TrajectoryCluster:
    signature: Signature
    trajectory_ids: list[str]


def cluster_trajectories(trajectories: list[Trajectory]) -> list[TrajectoryCluster]:
    groups: dict[Signature, list[str]] = defaultdict(list)
    for trajectory in trajectories:
        groups[structural_signature(trajectory)].append(trajectory.trajectory_id)
    return [
        TrajectoryCluster(signature=signature, trajectory_ids=sorted(ids))
        for signature, ids in sorted(groups.items())
    ]


def cluster_purity(clusters: list[TrajectoryCluster], labels: dict[str, str]) -> float:
    total = sum(len(cluster.trajectory_ids) for cluster in clusters)
    if total == 0:
        raise ValueError("cluster_purity requires at least one trajectory")
    majority = 0
    for cluster in clusters:
        counts: dict[str, int] = defaultdict(int)
        for trajectory_id in cluster.trajectory_ids:
            counts[labels[trajectory_id]] += 1
        majority += max(counts.values())
    return majority / total
