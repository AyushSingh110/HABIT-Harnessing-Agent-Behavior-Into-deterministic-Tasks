from pathlib import Path

import pytest
from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.eval import CorpusSummary, generate_corpus
from habit.storage import SqlAlchemyTrajectoryStore

DOMAINS = {"invoice", "ticket", "report"}


@pytest.fixture
def store(tmp_path: Path) -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )


def test_summary_shape(store: SqlAlchemyTrajectoryStore) -> None:
    summary = generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    assert isinstance(summary, CorpusSummary)
    assert summary.total == 60
    assert set(summary.per_domain) == DOMAINS
    for stats in summary.per_domain.values():
        assert stats.count == 20


def test_persistence(store: SqlAlchemyTrajectoryStore) -> None:
    summary = generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    for domain in DOMAINS:
        assert store.count(domain=domain) == 20
        assert summary.per_domain[domain].count == len(store.query(domain=domain))


def test_match_rate(store: SqlAlchemyTrajectoryStore) -> None:
    summary = generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    for stats in summary.per_domain.values():
        assert stats.match_rate == 1.0


def test_step_stats_sane(store: SqlAlchemyTrajectoryStore) -> None:
    summary = generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    for stats in summary.per_domain.values():
        assert stats.min_steps >= 1
        assert stats.min_steps <= stats.mean_steps <= stats.max_steps


def test_unique_ids_across_seeds(store: SqlAlchemyTrajectoryStore) -> None:
    first = generate_corpus(store, model=FakeModel(), per_domain=20, seed=1)
    second = generate_corpus(store, model=FakeModel(), per_domain=20, seed=2)
    assert first.total == 60
    assert second.total == 60
    assert store.count(domain="invoice") == 40


def test_determinism() -> None:
    def run() -> CorpusSummary:
        engine = create_engine("sqlite://")
        return generate_corpus(
            SqlAlchemyTrajectoryStore(engine), model=FakeModel(), per_domain=15, seed=7
        )

    a = run()
    b = run()
    assert a.total == b.total
    for domain in DOMAINS:
        assert a.per_domain[domain] == b.per_domain[domain]
