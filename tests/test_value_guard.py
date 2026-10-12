import math
from collections.abc import Callable

from sqlalchemy import create_engine

from habit.baseline import FakeModel, run_invoice_baseline, run_report_baseline
from habit.eval import detection_roc, roc_auc
from habit.eval.research import ShiftableWorkload
from habit.runtime import ValueGuard, learn_envelopes
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import InvoiceWorkload, ReportWorkload

CASES: list[tuple[ShiftableWorkload, Callable[..., Trajectory]]] = [
    (InvoiceWorkload(), run_invoice_baseline),
    (ReportWorkload(), run_report_baseline),
]


def _train(
    workload: ShiftableWorkload, runner: Callable[..., Trajectory]
) -> list[Trajectory]:
    tools = {tool.name: tool for tool in workload.tools()}
    store = SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))
    for i, task in enumerate(workload.generate(40, seed=0)):
        runner(
            task, model=FakeModel(), store=store, tools=tools, trajectory_id=f"t-{i}"
        )
    return store.query()


def test_learn_envelopes() -> None:
    envelopes = learn_envelopes(_train(InvoiceWorkload(), run_invoice_baseline))
    assert envelopes
    for envelope in envelopes.values():
        assert math.isfinite(envelope.lo) and math.isfinite(envelope.hi)
        assert envelope.lo <= envelope.hi
    # at least one numeric field varies across the corpus (lo < hi)
    assert any(env.lo < env.hi for env in envelopes.values())


def test_guard_flags_out_of_range() -> None:
    trajectories = _train(InvoiceWorkload(), run_invoice_baseline)
    envelopes = learn_envelopes(trajectories)
    (tool_name, field), envelope = next(iter(envelopes.items()))
    guard = ValueGuard(envelopes, tolerance=0.0)
    anomalous = {field: max(abs(envelope.lo), abs(envelope.hi), 1.0) * 100}
    assert guard.is_anomalous(tool_name, anomalous) is True
    in_range = {field: envelope.lo}
    assert guard.is_anomalous(tool_name, in_range) is False


def test_tolerance_monotone_suppression() -> None:
    trajectories = _train(InvoiceWorkload(), run_invoice_baseline)
    envelopes = learn_envelopes(trajectories)
    (tool_name, field), envelope = next(iter(envelopes.items()))
    result = {field: envelope.hi + max(abs(envelope.lo), abs(envelope.hi), 1.0) * 3}
    flags = [
        ValueGuard(envelopes, tolerance=t).is_anomalous(tool_name, result)
        for t in (0.0, 1.0, 2.0, 4.0, 100.0)
    ]
    ints = [int(f) for f in flags]
    assert ints == sorted(ints, reverse=True)


def test_detection_roc_shape() -> None:
    for workload, runner in CASES:
        points = detection_roc(workload, runner, n_train=40, n_eval=100)
        best_tol0 = next(p for p in points if p.tolerance == 0.0)
        assert best_tol0.tpr > 0.8
        assert best_tol0.fpr < 0.2
        highest_tol = max(points, key=lambda p: p.tolerance)
        assert highest_tol.tpr <= best_tol0.tpr
        assert highest_tol.fpr <= best_tol0.fpr
        # value guard dominates the structural (0,0) point: a positive-TPR low-FPR point
        assert any(p.tpr > 0.0 and p.fpr < 0.2 for p in points)


def test_roc_auc() -> None:
    points = detection_roc(InvoiceWorkload(), run_invoice_baseline)
    auc = roc_auc(points)
    assert 0.0 <= auc <= 1.0
    assert auc > 0.5


def test_determinism() -> None:
    a = detection_roc(InvoiceWorkload(), run_invoice_baseline)
    b = detection_roc(InvoiceWorkload(), run_invoice_baseline)
    assert a == b
