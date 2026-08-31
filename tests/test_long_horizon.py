from habit.compiler import cluster_trajectories
from habit.eval import generate_long_horizon, run_long_horizon_study


def test_generation_shape() -> None:
    trajectories = generate_long_horizon(20, count=4, seed=0)
    assert len(trajectories) == 4
    for trajectory in trajectories:
        assert len(trajectory.steps) == 20
    assert len(cluster_trajectories(trajectories)) == 1


def test_study_peaks_and_safety() -> None:
    result = run_long_horizon_study(n_steps=50)
    assert result.safe is True
    assert result.policy_peak == 2
    assert result.naive_peak == 50
    assert abs(result.token_savings_pct - (1 - 2 / 50)) < 1e-9


def test_survival_at_default_budget() -> None:
    result = run_long_horizon_study(n_steps=50)
    assert result.budget == result.policy_peak
    assert result.naive_survives is False
    assert result.policy_survives is True


def test_scaling() -> None:
    r50 = run_long_horizon_study(n_steps=50)
    r100 = run_long_horizon_study(n_steps=100)
    assert r100.policy_peak == 2
    assert r100.token_savings_pct > r50.token_savings_pct


def test_determinism() -> None:
    assert run_long_horizon_study(n_steps=40) == run_long_horizon_study(n_steps=40)
