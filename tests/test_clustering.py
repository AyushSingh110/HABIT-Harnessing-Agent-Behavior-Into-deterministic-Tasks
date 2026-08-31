from pathlib import Path

import pytest
from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import (
    TrajectoryCluster,
    cluster_purity,
    cluster_trajectories,
    structural_signature,
)
from habit.eval import generate_corpus
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore


@pytest.fixture
def trajectories(tmp_path: Path) -> list[Trajectory]:
    store = SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )
    generate_corpus(store, model=FakeModel(), per_domain=5, seed=1)
    return store.query()


def _by_domain(trajectories: list[Trajectory], domain: str) -> list[Trajectory]:
    return [t for t in trajectories if t.domain == domain]


def test_signature_same_and_different(trajectories: list[Trajectory]) -> None:
    invoices = _by_domain(trajectories, "invoice")
    tickets = _by_domain(trajectories, "ticket")
    assert structural_signature(invoices[0]) == structural_signature(invoices[1])
    assert structural_signature(invoices[0]) != structural_signature(tickets[0])


def test_three_pure_clusters(trajectories: list[Trajectory]) -> None:
    domain_by_id = {t.trajectory_id: t.domain for t in trajectories}
    clusters = cluster_trajectories(trajectories)
    assert len(clusters) == 3
    for cluster in clusters:
        domains = {domain_by_id[tid] for tid in cluster.trajectory_ids}
        assert len(domains) == 1


def test_purity_perfect(trajectories: list[Trajectory]) -> None:
    labels = {t.trajectory_id: t.domain for t in trajectories}
    clusters = cluster_trajectories(trajectories)
    assert cluster_purity(clusters, labels) == 1.0


def test_purity_mixed_cluster() -> None:
    cluster = TrajectoryCluster(
        signature=(("LLM_CALL", None),),
        trajectory_ids=["a", "b", "c", "d"],
    )
    labels = {"a": "x", "b": "x", "c": "x", "d": "y"}
    assert cluster_purity([cluster], labels) == 0.75


def test_determinism(trajectories: list[Trajectory]) -> None:
    assert cluster_trajectories(trajectories) == cluster_trajectories(trajectories)


def test_edge_cases() -> None:
    assert cluster_trajectories([]) == []
    with pytest.raises(ValueError):
        cluster_purity([], {})
