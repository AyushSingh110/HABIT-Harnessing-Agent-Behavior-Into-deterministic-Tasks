# Online loop: route to a monitored habit; fall back to the live agent on divergence.

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from habit.baseline.model import LargeModel
from habit.interfaces import TrajectoryStore
from habit.runtime.divergence import run_habit_checked
from habit.runtime.router import Router
from habit.schemas import Trajectory
from habit.workloads import MockTool, WorkloadTask


@dataclass(frozen=True)
class RuntimeResult:
    output: dict[str, Any]
    mode: str


def run_task(
    *,
    domain: str,
    task: WorkloadTask,
    trajectory_id: str,
    router: Router,
    expected: list[str | None],
    tools: dict[str, MockTool],
    baseline: Callable[..., Trajectory],
    model: LargeModel,
    store: TrajectoryStore,
) -> RuntimeResult:
    plan = router.route(domain, task.task_input)
    if plan is not None:
        output, report = run_habit_checked(plan, expected, task.task_input, tools)
        if not report.diverged and output is not None:
            return RuntimeResult(output=output, mode="habit")
        traj = baseline(
            task, model=model, store=store, tools=tools, trajectory_id=trajectory_id
        )
        return RuntimeResult(output=traj.outcome.final_output, mode="fallback")

    traj = baseline(
        task, model=model, store=store, tools=tools, trajectory_id=trajectory_id
    )
    return RuntimeResult(output=traj.outcome.final_output, mode="live")
