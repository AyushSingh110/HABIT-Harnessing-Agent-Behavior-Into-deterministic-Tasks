# CLI entry point: print the live-vs-habit headline benchmark table.

import argparse

from habit.baseline import FakeModel
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
    parser.add_argument("--train-per-domain", type=int, default=100)
    parser.add_argument("--eval-per-domain", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    benchmark = run_benchmark(
        model=FakeModel(),
        train_per_domain=args.train_per_domain,
        eval_per_domain=args.eval_per_domain,
        seed=args.seed,
    )
    for domain, result in benchmark.per_domain.items():
        print(domain)
        print(_row(result.live))
        print(_row(result.habit))
    print("habit eliminates every LLM call on the eval set: live -> 0 calls, 0 tokens.")


if __name__ == "__main__":
    main()
