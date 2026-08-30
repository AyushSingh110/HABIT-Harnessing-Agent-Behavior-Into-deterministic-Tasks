# CLI entry point: fill the configured database with baseline trajectories.

import argparse

from habit.baseline import FakeModel
from habit.eval import generate_corpus
from habit.storage import SqlAlchemyTrajectoryStore, engine_from_env


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a baseline trajectory corpus."
    )
    parser.add_argument("--per-domain", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    store = SqlAlchemyTrajectoryStore(engine_from_env())
    summary = generate_corpus(
        store, model=FakeModel(), per_domain=args.per_domain, seed=args.seed
    )

    for domain, stats in summary.per_domain.items():
        print(
            f"{domain:8s} count={stats.count} match_rate={stats.match_rate:.3f} "
            f"steps(mean/min/max)={stats.mean_steps:.1f}/{stats.min_steps}/{stats.max_steps}"
        )
    print(f"total={summary.total}")


if __name__ == "__main__":
    main()
