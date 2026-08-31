# Replay-validation gate: a habit is usable only if it reproduces held-out outputs.

from dataclasses import dataclass

from habit.compiler.clustering import TrajectoryCluster
from habit.compiler.crystallizer import HabitPlan, crystallize, run_habit
from habit.schemas import Trajectory
from habit.workloads import MockTool


@dataclass(frozen=True)
class ValidationResult:
    checked: int
    matched: int
    mismatched_ids: tuple[str, ...]
    passed: bool


@dataclass(frozen=True)
class CompiledHabit:
    plan: HabitPlan
    validation: ValidationResult

    @property
    def usable(self) -> bool:
        return self.validation.passed


def validate_habit(
    plan: HabitPlan,
    trajectories: list[Trajectory],
    tools: dict[str, MockTool],
    *,
    threshold: float = 1.0,
) -> ValidationResult:
    checked = 0
    matched = 0
    mismatched: list[str] = []
    for trajectory in trajectories:
        if trajectory.outcome.ground_truth_match is not True:
            continue
        checked += 1
        output = run_habit(plan, trajectory.task_input, tools)
        if output == trajectory.outcome.final_output:
            matched += 1
        else:
            mismatched.append(trajectory.trajectory_id)
    passed = checked > 0 and matched / checked >= threshold
    return ValidationResult(
        checked=checked,
        matched=matched,
        mismatched_ids=tuple(mismatched),
        passed=passed,
    )


def compile_habit(
    cluster: TrajectoryCluster,
    trajectories_by_id: dict[str, Trajectory],
    tools: dict[str, MockTool],
    *,
    validation_fraction: float = 0.3,
    threshold: float = 1.0,
) -> CompiledHabit:
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
    plan = crystallize(training_cluster, trajectories_by_id)
    validation = validate_habit(
        plan,
        [trajectories_by_id[tid] for tid in validation_ids],
        tools,
        threshold=threshold,
    )
    return CompiledHabit(plan=plan, validation=validation)
