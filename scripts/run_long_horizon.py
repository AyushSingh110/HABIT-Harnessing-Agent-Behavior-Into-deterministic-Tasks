# CLI entry point: print the long-horizon naive-vs-policy survival result.

import argparse

from habit.eval import run_long_horizon_study


def main() -> None:
    parser = argparse.ArgumentParser(description="Long-horizon context survival study.")
    parser.add_argument("--n-steps", type=int, default=50)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    result = run_long_horizon_study(
        n_steps=args.n_steps, count=args.count, seed=args.seed
    )
    print(f"n_steps={result.n_steps} safe={result.safe}")
    print(f"  naive_peak={result.naive_peak} policy_peak={result.policy_peak}")
    print(f"  token_savings={result.token_savings_pct:.1%}")
    print(
        f"  at budget={result.budget}: naive_survives={result.naive_survives} "
        f"policy_survives={result.policy_survives}"
    )


if __name__ == "__main__":
    main()
