from collections.abc import Callable

from habit.baseline import (
    run_invoice_baseline,
    run_report_baseline,
    run_ticket_baseline,
)
from habit.eval import generalization_gap, safety_under_shift
from habit.eval.research import ShiftableWorkload
from habit.schemas import Trajectory
from habit.workloads import InvoiceWorkload, ReportWorkload, TicketWorkload

DOMAINS: list[tuple[ShiftableWorkload, Callable[..., Trajectory]]] = [
    (InvoiceWorkload(), run_invoice_baseline),
    (TicketWorkload(), run_ticket_baseline),
    (ReportWorkload(), run_report_baseline),
]


def test_generalization_across_shift() -> None:
    for workload, runner in DOMAINS:
        result = generalization_gap(workload, runner, train_n=20, eval_n=20)
        assert result.domain == workload.domain
        assert result.normal_success == 1.0
        assert result.shifted_success == 1.0


def test_safety_under_shift() -> None:
    for workload, runner in DOMAINS:
        result = safety_under_shift(workload, runner, train_n=20, eval_n=20)
        assert result.domain == workload.domain
        assert result.normal_safe is True
        assert result.shifted_safe is True
        assert result.shifted_starvations == 0


def test_determinism() -> None:
    workload, runner = DOMAINS[0]
    assert generalization_gap(workload, runner, train_n=20, eval_n=20) == (
        generalization_gap(workload, runner, train_n=20, eval_n=20)
    )
    assert safety_under_shift(workload, runner, train_n=20, eval_n=20) == (
        safety_under_shift(workload, runner, train_n=20, eval_n=20)
    )
