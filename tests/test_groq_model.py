from habit.baseline import FakeModel, GroqModel, LargeModel
from habit.eval import run_benchmark


def test_provider_and_model() -> None:
    assert GroqModel().provider == "groq"
    assert GroqModel().model == "llama-3.3-70b-versatile"
    assert GroqModel("llama-3.1-8b-instant").model == "llama-3.1-8b-instant"


def test_satisfies_protocol() -> None:
    model: LargeModel = GroqModel()
    assert model.provider == "groq"


def test_benchmark_with_train_model() -> None:
    benchmark = run_benchmark(
        model=FakeModel(),
        train_model=FakeModel(),
        train_per_domain=20,
        eval_per_domain=10,
    )
    assert set(benchmark.per_domain) == {"invoice", "ticket", "report"}
    for result in benchmark.per_domain.values():
        assert result.habit.mean_llm_calls == 0.0
        assert result.habit.mean_tokens == 0.0
        assert result.live.mean_llm_calls > 0
        assert result.live.success_rate == 1.0
        assert result.habit.success_rate == 1.0


def test_benchmark_train_model_defaults_to_model() -> None:
    benchmark = run_benchmark(
        model=FakeModel(), train_per_domain=20, eval_per_domain=10
    )
    assert benchmark.per_domain["invoice"].live.tasks == 10
