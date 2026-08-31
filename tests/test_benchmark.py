from habit.baseline import FakeModel
from habit.eval import Benchmark, run_benchmark

DOMAINS = {"invoice", "ticket", "report"}
EXPECTED_LLM_CALLS = {"invoice": 5.0, "ticket": 6.0, "report": 6.0}


def _run() -> Benchmark:
    return run_benchmark(
        model=FakeModel(), train_per_domain=30, eval_per_domain=20, seed=0
    )


def test_domains() -> None:
    assert set(_run().per_domain) == DOMAINS


def test_habit_makes_no_model_calls() -> None:
    benchmark = _run()
    for result in benchmark.per_domain.values():
        assert result.habit.mean_llm_calls == 0.0
        assert result.habit.mean_tokens == 0.0
        assert result.live.mean_llm_calls > 0
        assert result.live.mean_tokens > 0


def test_success_parity() -> None:
    benchmark = _run()
    for result in benchmark.per_domain.values():
        assert result.live.success_rate == 1.0
        assert result.habit.success_rate == 1.0


def test_task_counts() -> None:
    benchmark = _run()
    for result in benchmark.per_domain.values():
        assert result.live.tasks == 20
        assert result.habit.tasks == 20


def test_expected_llm_calls() -> None:
    benchmark = _run()
    for domain, expected in EXPECTED_LLM_CALLS.items():
        assert benchmark.per_domain[domain].live.mean_llm_calls == expected


def test_non_negative_latency() -> None:
    benchmark = _run()
    for result in benchmark.per_domain.values():
        assert result.live.mean_latency_ms >= 0
        assert result.habit.mean_latency_ms >= 0


def test_metric_determinism() -> None:
    a = _run()
    b = _run()
    for domain in DOMAINS:
        for system in ("live", "habit"):
            m_a = getattr(a.per_domain[domain], system)
            m_b = getattr(b.per_domain[domain], system)
            assert m_a.success_rate == m_b.success_rate
            assert m_a.mean_llm_calls == m_b.mean_llm_calls
            assert m_a.mean_tokens == m_b.mean_tokens
