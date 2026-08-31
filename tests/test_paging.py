from pathlib import Path

import pytest
from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import cluster_trajectories
from habit.context import (
    ContextPolicy,
    PagingTrace,
    induce_context_policy,
    simulate_paging,
    survives,
    working_set_sizes,
)
from habit.eval import generate_corpus
from habit.schemas import Trajectory
from habit.storage import SqlAlchemyTrajectoryStore


def _policies(tmp_path: Path) -> dict[str, ContextPolicy]:
    store = SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )
    generate_corpus(store, model=FakeModel(), per_domain=10, seed=1)
    trajectories: list[Trajectory] = store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    policies: dict[str, ContextPolicy] = {}
    for cluster in cluster_trajectories(trajectories):
        domain = by_id[cluster.trajectory_ids[0]].domain
        policies[domain] = induce_context_policy(cluster, by_id)
    return policies


def _items(policy: ContextPolicy) -> set[str]:
    items: set[str] = set()
    for step in policy.steps:
        items |= set(step.live) | set(step.evictable)
    return items


def _uniform(policy: ContextPolicy) -> dict[str, int]:
    return {item: 1 for item in _items(policy)}


def test_uniform_matches_counts(tmp_path: Path) -> None:
    policy = _policies(tmp_path)["invoice"]
    trace = simulate_paging(policy, _uniform(policy))
    peak_naive, peak_policy = working_set_sizes(policy)
    assert trace.naive_peak == peak_naive == 5
    assert trace.policy_peak == peak_policy == 4
    for naive, pol in zip(trace.naive_tokens_per_step, trace.policy_tokens_per_step):
        assert pol <= naive


def test_varied_sizes(tmp_path: Path) -> None:
    policy = _policies(tmp_path)["invoice"]
    sizes = {item: 1 for item in _items(policy)}
    sizes["invoice"] = 100
    trace = simulate_paging(policy, sizes)
    assert trace.policy_peak < trace.naive_peak
    for naive, pol in zip(trace.naive_tokens_per_step, trace.policy_tokens_per_step):
        assert pol <= naive


def test_survives(tmp_path: Path) -> None:
    policy = _policies(tmp_path)["invoice"]
    trace = simulate_paging(policy, _uniform(policy))
    assert survives(trace, 4) == (False, True)
    assert survives(trace, trace.naive_peak) == (True, True)
    assert survives(trace, trace.policy_peak - 1) == (False, False)


def test_all_domains_policy_smaller(tmp_path: Path) -> None:
    for policy in _policies(tmp_path).values():
        trace = simulate_paging(policy, _uniform(policy))
        assert trace.policy_peak < trace.naive_peak


def test_missing_size_raises(tmp_path: Path) -> None:
    policy = _policies(tmp_path)["invoice"]
    sizes = _uniform(policy)
    del sizes["invoice"]
    with pytest.raises(ValueError):
        simulate_paging(policy, sizes)


def test_determinism(tmp_path: Path) -> None:
    policy = _policies(tmp_path)["invoice"]
    sizes = _uniform(policy)
    assert simulate_paging(policy, sizes) == simulate_paging(policy, sizes)


def test_empty_policy() -> None:
    trace = simulate_paging(ContextPolicy(signature=(), steps=[]), {})
    assert trace == PagingTrace(
        naive_tokens_per_step=(),
        policy_tokens_per_step=(),
        naive_peak=0,
        policy_peak=0,
    )
