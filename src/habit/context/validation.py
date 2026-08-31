# Context-policy correctness gate: safe only if it never starves a held-out run.

from dataclasses import dataclass

from habit.compiler import TrajectoryCluster
from habit.context.policy import ContextPolicy, induce_context_policy
from habit.schemas import Trajectory


@dataclass(frozen=True)
class ContextValidation:
    checked_steps: int
    starved_steps: int
    starvations: tuple[tuple[str, int, tuple[str, ...]], ...]
    safe: bool


@dataclass(frozen=True)
class ValidatedContextPolicy:
    policy: ContextPolicy
    validation: ContextValidation

    @property
    def safe(self) -> bool:
        return self.validation.safe


def validate_context_policy(
    policy: ContextPolicy, trajectories: list[Trajectory]
) -> ContextValidation:
    checked_steps = 0
    starvations: list[tuple[str, int, tuple[str, ...]]] = []
    for trajectory in trajectories:
        if len(trajectory.steps) != len(policy.steps):
            raise ValueError(
                f"trajectory step count differs from policy: {trajectory.trajectory_id}"
            )
        for i, step in enumerate(trajectory.steps):
            checked_steps += 1
            missing = set(step.context_reads) - set(policy.steps[i].live)
            if missing:
                starvations.append(
                    (trajectory.trajectory_id, i, tuple(sorted(missing)))
                )
    safe = checked_steps > 0 and len(starvations) == 0
    return ContextValidation(
        checked_steps=checked_steps,
        starved_steps=len(starvations),
        starvations=tuple(starvations),
        safe=safe,
    )


def induce_and_validate_policy(
    cluster: TrajectoryCluster,
    trajectories_by_id: dict[str, Trajectory],
    *,
    validation_fraction: float = 0.3,
) -> ValidatedContextPolicy:
    ids = sorted(cluster.trajectory_ids)
    n_val = max(1, int(len(ids) * validation_fraction))
    validation_ids = ids[:n_val]
    training_ids = ids[n_val:]
    if not training_ids:
        raise ValueError(
            "training set is empty; reduce validation_fraction or add trajectories"
        )

    training_cluster = TrajectoryCluster(
        signature=cluster.signature, trajectory_ids=training_ids
    )
    policy = induce_context_policy(training_cluster, trajectories_by_id)
    validation = validate_context_policy(
        policy, [trajectories_by_id[tid] for tid in validation_ids]
    )
    return ValidatedContextPolicy(policy=policy, validation=validation)
