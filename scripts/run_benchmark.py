# CLI entry point: print the live-vs-habit headline benchmark table.

import argparse

from habit.baseline import FakeModel, GroqModel, LargeModel, OllamaModel
from habit.eval import SystemMetrics, run_benchmark


def _row(metrics: SystemMetrics) -> str:
    return (
        f"  {metrics.system:5s} success={metrics.success_rate:.3f} "
        f"llm_calls={metrics.mean_llm_calls:.2f} tokens={metrics.mean_tokens:.1f} "
        f"latency_ms={metrics.mean_latency_ms:.3f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark live baseline vs compiled habit."
    )
    parser.add_argument("--model", choices=["fake", "groq", "ollama"], default="fake")
    parser.add_argument("--groq-model", default="llama-3.3-70b-versatile")
    parser.add_argument("--ollama-model", default="llama3.1:8b")
    parser.add_argument("--train-per-domain", type=int, default=100)
    parser.add_argument("--eval-per-domain", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if args.model == "groq":
        model: LargeModel = GroqModel(args.groq_model)
        train_model: LargeModel | None = FakeModel()
    elif args.model == "ollama":
        model = OllamaModel(args.ollama_model)
        train_model = FakeModel()
    else:
        model = FakeModel()
        train_model = None

    benchmark = run_benchmark(
        model=model,
        train_model=train_model,
        train_per_domain=args.train_per_domain,
        eval_per_domain=args.eval_per_domain,
        seed=args.seed,
    )
    for domain, result in benchmark.per_domain.items():
        print(domain)
        print(_row(result.live))
        print(_row(result.habit))
    calls = benchmark.per_domain["invoice"].live.mean_llm_calls
    print(f"live makes ~{calls:.0f} real API calls/task; habit makes 0.")


if __name__ == "__main__":
    main()
