# Skeleton induction: extract the per-step stable recipe shared across a cluster.

from dataclasses import dataclass

from habit.compiler.clustering import Signature, TrajectoryCluster, structural_signature
from habit.schemas import Trajectory


@dataclass(frozen=True)
class SkeletonStep:
    index: int
    step_type: str
    tool_name: str | None
    context_reads: tuple[str, ...]
    result_fingerprint: str | None
    stable: bool


@dataclass(frozen=True)
class Skeleton:
    signature: Signature
    steps: list[SkeletonStep]
    support: int


def induce_skeleton(
    cluster: TrajectoryCluster, trajectories_by_id: dict[str, Trajectory]
) -> Skeleton:
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

    steps: list[SkeletonStep] = []
    for i, (step_type, tool_name) in enumerate(cluster.signature):
        reads = [tuple(t.steps[i].context_reads) for t in trajectories]
        reads_stable = all(r == reads[0] for r in reads)

        fingerprints = [t.steps[i].tool_result_schema_fingerprint for t in trajectories]
        fp_stable = fingerprints[0] is not None and all(
            fp == fingerprints[0] for fp in fingerprints
        )
        result_fingerprint = fingerprints[0] if fp_stable else None

        steps.append(
            SkeletonStep(
                index=i,
                step_type=step_type,
                tool_name=tool_name,
                context_reads=reads[0] if reads_stable else (),
                result_fingerprint=result_fingerprint,
                stable=step_type == "TOOL_CALL"
                and reads_stable
                and result_fingerprint is not None,
            )
        )
    return Skeleton(
        signature=cluster.signature, steps=steps, support=len(cluster.trajectory_ids)
    )
