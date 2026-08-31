# CLI entry point: run the invoice adversarial-injection study and print the rates.

from typing import Any

from sqlalchemy import create_engine

from habit.baseline import FakeModel
from habit.compiler import cluster_trajectories, compile_habit, induce_skeleton
from habit.eval import generate_corpus, run_injection_study
from habit.runtime import expected_tool_fingerprints
from habit.storage import SqlAlchemyTrajectoryStore
from habit.workloads import InvoiceWorkload, MockTool


def _shape_injector(tools: dict[str, MockTool]) -> dict[str, MockTool]:
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        return {**real(**kwargs), "EXTRA": 1}

    return {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}


def _value_injector(tools: dict[str, MockTool]) -> dict[str, MockTool]:
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        result = real(**kwargs)
        return {**result, "totals_valid": not result["totals_valid"]}

    return {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}


def main() -> None:
    workload = InvoiceWorkload()
    tools = {tool.name: tool for tool in workload.tools()}
    store = SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))
    generate_corpus(store, model=FakeModel(), per_domain=100, seed=0)
    trajectories = store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = next(
        c
        for c in cluster_trajectories(trajectories)
        if by_id[c.trajectory_ids[0]].domain == "invoice"
    )
    plan = compile_habit(cluster, by_id, tools).plan
    expected = expected_tool_fingerprints(induce_skeleton(cluster, by_id))
    tasks = workload.generate(50, seed=10_000)

    stats = run_injection_study(
        plan,
        expected,
        tasks,
        tools,
        shape_injector=_shape_injector,
        value_injector=_value_injector,
    )
    print(f"false_abort_rate={stats.false_abort_rate:.3f}")
    print(f"shape_catch_rate={stats.shape_catch_rate:.3f}")
    print(f"value_catch_rate={stats.value_catch_rate:.3f}")


if __name__ == "__main__":
    main()
