import math
from collections.abc import Callable

from habit.baseline import run_invoice_baseline, run_ticket_baseline
from habit.eval import SemanticCache, compare_strategies
from habit.eval.research import ShiftableWorkload
from habit.schemas import Trajectory
from habit.workloads import InvoiceWorkload, TicketWorkload

CASES: list[tuple[ShiftableWorkload, Callable[..., Trajectory]]] = [
    (InvoiceWorkload(), run_invoice_baseline),
    (TicketWorkload(), run_ticket_baseline),
]


def test_semantic_cache_exact_match() -> None:
    cache = SemanticCache()
    assert cache.get({"a": 1}) is None
    cache.put({"a": 1}, {"out": 2})
    assert cache.get({"a": 1}) == {"out": 2}
    assert cache.get({"a": 2}) is None


def test_reuse_rates() -> None:
    n, repeat_fraction = 40, 0.25
    expected_cache = math.floor(n * repeat_fraction) / n
    for workload, runner in CASES:
        results = compare_strategies(
            workload, runner, n=n, repeat_fraction=repeat_fraction
        )
        assert results["vanilla"].reuse_rate == 0.0
        assert abs(results["cache"].reuse_rate - expected_cache) <= 1 / n
        assert results["habit"].reuse_rate == 1.0


def test_cost_ordering() -> None:
    for workload, runner in CASES:
        results = compare_strategies(workload, runner, n=40, repeat_fraction=0.25)
        vanilla = results["vanilla"].mean_live_llm_calls
        cache = results["cache"].mean_live_llm_calls
        habit = results["habit"].mean_live_llm_calls
        assert vanilla > 0
        assert habit == 0.0
        assert habit < cache < vanilla


def test_correctness() -> None:
    for workload, runner in CASES:
        results = compare_strategies(workload, runner, n=40, repeat_fraction=0.25)
        assert results["vanilla"].success_rate == 1.0
        assert results["cache"].success_rate == 1.0
        assert results["habit"].success_rate == 1.0


def test_determinism() -> None:
    workload, runner = CASES[0]
    a = compare_strategies(workload, runner, n=40, repeat_fraction=0.25)
    b = compare_strategies(workload, runner, n=40, repeat_fraction=0.25)
    assert a == b
