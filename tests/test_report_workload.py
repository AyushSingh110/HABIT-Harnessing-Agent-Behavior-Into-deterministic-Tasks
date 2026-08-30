from typing import Any

from habit.workloads import ReportWorkload, WorkloadGenerator
from habit.workloads.report import (
    SHIFTED_PERIODS,
    SHIFTED_REGIONS,
    aggregate,
    fetch_records,
    filter_records,
    rank_metrics,
)


def _recompute(request: dict[str, Any]) -> dict[str, Any]:
    matching = [
        r
        for r in request["records"]
        if r["region"] == request["region"] and r["period"] == request["period"]
    ]
    totals: dict[str, int] = {}
    grand_total = 0
    for record in matching:
        totals[record["metric"]] = totals.get(record["metric"], 0) + record["value"]
        grand_total += record["value"]
    top_metric = min(totals, key=lambda m: (-totals[m], m))
    return {
        "totals": totals,
        "record_count": len(matching),
        "grand_total": grand_total,
        "top_metric": top_metric,
    }


def test_conformance_and_domain() -> None:
    gen: WorkloadGenerator = ReportWorkload()
    assert gen.domain == "report"


def test_determinism() -> None:
    assert ReportWorkload().generate(6, seed=4) == ReportWorkload().generate(6, seed=4)
    assert ReportWorkload().generate(
        6, seed=4, shifted=True
    ) == ReportWorkload().generate(6, seed=4, shifted=True)


def test_different_seed_differs() -> None:
    assert ReportWorkload().generate(6, seed=4) != ReportWorkload().generate(6, seed=7)


def test_self_consistency() -> None:
    for task in ReportWorkload().generate(30, seed=13):
        recomputed = _recompute(task.task_input)
        assert task.expected["totals"] == recomputed["totals"]
        assert task.expected["record_count"] == recomputed["record_count"]
        assert task.expected["grand_total"] == recomputed["grand_total"]
        assert task.expected["top_metric"] == recomputed["top_metric"]
        assert task.expected["totals"]  # non-empty


def test_filtering_matters() -> None:
    tasks = ReportWorkload().generate(30, seed=13)
    assert any(
        task.expected["record_count"] < len(task.task_input["records"])
        for task in tasks
    )


def test_shifted_split() -> None:
    tasks = ReportWorkload().generate(20, seed=8, shifted=True)
    for task in tasks:
        assert task.task_input["region"] in SHIFTED_REGIONS
        assert task.task_input["period"] in SHIFTED_PERIODS
        assert task.expected["totals"]
        assert task.expected == {
            "report_id": task.expected["report_id"],
            **_recompute(task.task_input),
        }


def test_tools() -> None:
    records = [
        {"region": "north", "period": "2026-Q1", "metric": "sales", "value": 100},
        {"region": "north", "period": "2026-Q1", "metric": "returns", "value": 40},
        {"region": "south", "period": "2026-Q1", "metric": "sales", "value": 999},
    ]
    request = {
        "report_id": "RPT-1",
        "region": "north",
        "period": "2026-Q1",
        "records": records,
    }
    assert fetch_records(request) == {"records": records}

    filtered = filter_records(records, "north", "2026-Q1")["records"]
    assert filtered == records[:2]

    agg = aggregate(filtered)
    assert agg == {
        "totals": {"sales": 100, "returns": 40},
        "record_count": 2,
        "grand_total": 140,
    }

    assert rank_metrics(agg["totals"]) == {"top_metric": "sales"}
    assert rank_metrics({"beta": 50, "alpha": 50}) == {"top_metric": "alpha"}


def test_checker() -> None:
    workload = ReportWorkload()
    checker = workload.checker()
    task = workload.generate(1, seed=2)[0]
    assert checker(task, dict(task.expected)) is True
    wrong = dict(task.expected)
    wrong["grand_total"] = wrong["grand_total"] + 1
    assert checker(task, wrong) is False
