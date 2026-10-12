from collections.abc import Callable

import pytest

from habit.baseline import (
    LargeModel,
    ModelFailure,
    UnreliableModel,
    run_invoice_baseline,
    run_ticket_baseline,
)
from habit.eval import reliability_study
from habit.eval.research import ShiftableWorkload
from habit.schemas import Trajectory
from habit.workloads import InvoiceWorkload, TicketWorkload

CASES: list[tuple[ShiftableWorkload, Callable[..., Trajectory]]] = [
    (InvoiceWorkload(), run_invoice_baseline),
    (TicketWorkload(), run_ticket_baseline),
]


def test_unreliable_model() -> None:
    reliable = UnreliableModel(reliability=1.0)
    for _ in range(50):
        reliable.complete("step 0")
    always_fail = UnreliableModel(reliability=0.0)
    with pytest.raises(ModelFailure):
        always_fail.complete("step 0")
    m: LargeModel = UnreliableModel(reliability=1.0)
    assert m.provider == "fake-unreliable"


def test_study_perfect_reliability() -> None:
    results = reliability_study(
        InvoiceWorkload(), run_invoice_baseline, reliabilities=(1.0,), n_tasks=30
    )
    assert results[0].live_success_rate == 1.0
    assert results[0].habit_success_rate == 1.0


def test_study_degraded_reliability() -> None:
    results = reliability_study(
        InvoiceWorkload(), run_invoice_baseline, reliabilities=(0.9,), n_tasks=40
    )
    result = results[0]
    assert result.habit_success_rate == 1.0
    assert result.live_success_rate < 1.0
    assert abs(result.live_success_rate - 0.9**result.llm_calls) <= 0.2


def test_live_monotonic_in_reliability() -> None:
    for workload, runner in CASES:
        results = reliability_study(workload, runner, n_tasks=40)
        live = [r.live_success_rate for r in results]
        assert live == sorted(live)


def test_habit_immune_all_levels() -> None:
    for workload, runner in CASES:
        for result in reliability_study(workload, runner, n_tasks=30):
            assert result.habit_success_rate == 1.0


def test_determinism() -> None:
    a = reliability_study(InvoiceWorkload(), run_invoice_baseline, n_tasks=30)
    b = reliability_study(InvoiceWorkload(), run_invoice_baseline, n_tasks=30)
    assert a == b
