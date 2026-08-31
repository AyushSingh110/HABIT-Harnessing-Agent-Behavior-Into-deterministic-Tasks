# Crystallizer: induce provenance by value-matching; run habits with no LLM.

from dataclasses import dataclass
from typing import Any

from habit.compiler.clustering import TrajectoryCluster, structural_signature
from habit.schemas import Trajectory
from habit.workloads import MockTool


@dataclass(frozen=True)
class InputWhole:
    pass


@dataclass(frozen=True)
class InputField:
    key: str


@dataclass(frozen=True)
class ResultField:
    ordinal: int
    key: str


@dataclass(frozen=True)
class ResultWhole:
    ordinal: int


@dataclass(frozen=True)
class Const:
    value: Any


Source = InputWhole | InputField | ResultField | ResultWhole | Const


@dataclass(frozen=True)
class HabitStep:
    tool_name: str
    arg_sources: dict[str, Source]


@dataclass(frozen=True)
class HabitPlan:
    domain: str
    steps: list[HabitStep]
    output_assembly: dict[str, Source]


def _resolve(source: Source, task_input: dict[str, Any], results: list[Any]) -> Any:
    if isinstance(source, InputWhole):
        return task_input
    if isinstance(source, InputField):
        return task_input[source.key]
    if isinstance(source, ResultField):
        return results[source.ordinal][source.key]
    if isinstance(source, ResultWhole):
        return results[source.ordinal]
    return source.value


# First provenance Source (fixed priority) that explains the target in every trajectory.
def _induce(
    targets: list[Any],
    task_inputs: list[dict[str, Any]],
    results_per_traj: list[list[Any]],
    available: int,
    what: str,
) -> Source:
    candidates: list[Source] = [InputField(key) for key in sorted(task_inputs[0])]
    candidates.append(InputWhole())
    for ordinal in range(available):
        sample = results_per_traj[0][ordinal]
        if isinstance(sample, dict):
            candidates.extend(ResultField(ordinal, key) for key in sorted(sample))
    candidates.extend(ResultWhole(ordinal) for ordinal in range(available))

    for source in candidates:
        if all(
            _resolve(source, task_input, results) == target
            for task_input, results, target in zip(
                task_inputs, results_per_traj, targets
            )
        ):
            return source
    if all(target == targets[0] for target in targets):
        return Const(targets[0])
    raise ValueError(f"cannot induce a provenance source for {what}")


def crystallize(
    cluster: TrajectoryCluster, trajectories_by_id: dict[str, Trajectory]
) -> HabitPlan:
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

    task_inputs = [t.task_input for t in trajectories]
    tool_calls = [
        [step.tool_call for step in t.steps if step.tool_call is not None]
        for t in trajectories
    ]
    results_per_traj = [[call.result for call in calls] for calls in tool_calls]
    final_outputs = [t.outcome.final_output for t in trajectories]

    steps: list[HabitStep] = []
    for k in range(len(tool_calls[0])):
        tool_name = tool_calls[0][k].tool_name
        arg_sources: dict[str, Source] = {}
        for arg_key in tool_calls[0][k].arguments:
            targets = [calls[k].arguments[arg_key] for calls in tool_calls]
            arg_sources[arg_key] = _induce(
                targets, task_inputs, results_per_traj, k, f"{tool_name}.{arg_key}"
            )
        steps.append(HabitStep(tool_name=tool_name, arg_sources=arg_sources))

    output_assembly: dict[str, Source] = {}
    for out_key in final_outputs[0]:
        targets = [output[out_key] for output in final_outputs]
        output_assembly[out_key] = _induce(
            targets,
            task_inputs,
            results_per_traj,
            len(tool_calls[0]),
            f"output.{out_key}",
        )

    return HabitPlan(
        domain=trajectories[0].domain, steps=steps, output_assembly=output_assembly
    )


def run_habit(
    plan: HabitPlan, task_input: dict[str, Any], tools: dict[str, MockTool]
) -> dict[str, Any]:
    results: list[Any] = []
    for step in plan.steps:
        kwargs = {
            key: _resolve(source, task_input, results)
            for key, source in step.arg_sources.items()
        }
        results.append(tools[step.tool_name](**kwargs))
    return {
        out_key: _resolve(source, task_input, results)
        for out_key, source in plan.output_assembly.items()
    }
