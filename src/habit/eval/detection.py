# Detection ROC: sweep the value guard's tolerance to trade off TPR vs FPR.

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.eval.research import ShiftableWorkload
from habit.runtime import ValueEnvelope, ValueGuard, learn_envelopes
from habit.runtime.value_guard import _numeric_fields
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore

Runner = Callable[..., Trajectory]


@dataclass(frozen=True)
class DetectionPoint:
    tolerance: float
    tpr: float
    fpr: float


def _memory_store() -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))


def _tool_results(
    workload: ShiftableWorkload,
    runner: Runner,
    tools: dict[str, Any],
    *,
    n: int,
    seed: int,
) -> list[tuple[str, dict[str, Any]]]:
    store = _memory_store()
    results: list[tuple[str, dict[str, Any]]] = []
    for i, task in enumerate(workload.generate(n, seed=seed)):
        traj = runner(
            task, model=FakeModel(), store=store, tools=tools, trajectory_id=f"eval-{i}"
        )
        for step in traj.steps:
            if step.tool_call is not None and isinstance(step.tool_call.result, dict):
                results.append((step.tool_call.tool_name, step.tool_call.result))
    return results


# Corrupt one numeric field (keeping the result's shape) to an out-of-range value.
def _perturb(
    tool_name: str,
    result: dict[str, Any],
    envelopes: dict[tuple[str, str], ValueEnvelope],
    magnitude: float,
) -> dict[str, Any] | None:
    for field, _ in _numeric_fields(result):
        envelope = envelopes.get((tool_name, field))
        if envelope is not None:
            scale = max(abs(envelope.lo), abs(envelope.hi), 1.0)
            return {**result, field: scale * magnitude}
    return None


def detection_roc(
    workload: ShiftableWorkload,
    runner: Runner,
    *,
    tolerances: tuple[float, ...] = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0),
    n_train: int = 40,
    n_eval: int = 100,
    anomaly_magnitude: float = 100.0,
    seed: int = 0,
) -> list[DetectionPoint]:
    tools = {tool.name: tool for tool in workload.tools()}
    train_store = _memory_store()
    for i, task in enumerate(workload.generate(n_train, seed=seed)):
        runner(
            task,
            model=FakeModel(),
            store=train_store,
            tools=tools,
            trajectory_id=f"train-{i}",
        )
    envelopes = learn_envelopes(train_store.query())

    eval_results = _tool_results(workload, runner, tools, n=n_eval, seed=seed + 1)
    normals: list[tuple[str, dict[str, Any]]] = []
    anomalies: list[tuple[str, dict[str, Any]]] = []
    for i, (tool_name, result) in enumerate(eval_results):
        if i % 2 == 0:
            normals.append((tool_name, result))
        else:
            corrupted = _perturb(tool_name, result, envelopes, anomaly_magnitude)
            if corrupted is not None:
                anomalies.append((tool_name, corrupted))

    if not anomalies:
        raise ValueError(
            f"no numeric tool-result fields to perturb in domain {workload.domain!r}"
        )

    points: list[DetectionPoint] = []
    for tolerance in tolerances:
        guard = ValueGuard(envelopes, tolerance=tolerance)
        tp = sum(guard.is_anomalous(tn, r) for tn, r in anomalies)
        fp = sum(guard.is_anomalous(tn, r) for tn, r in normals)
        points.append(
            DetectionPoint(
                tolerance=tolerance,
                tpr=tp / len(anomalies),
                fpr=fp / len(normals),
            )
        )
    return sorted(points, key=lambda p: (p.fpr, p.tpr))


def roc_auc(points: list[DetectionPoint]) -> float:
    curve = sorted({(0.0, 0.0), (1.0, 1.0), *((p.fpr, p.tpr) for p in points)})
    area = 0.0
    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        area += (x1 - x0) * (y0 + y1) / 2
    return area
