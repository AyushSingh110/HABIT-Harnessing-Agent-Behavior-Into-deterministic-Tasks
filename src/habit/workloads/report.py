# Report workload (Domain 3): multi-step fetch/filter/aggregate/rank/format.

import random
from typing import Any

from habit.workloads.base import GroundTruthChecker, MockTool, WorkloadTask

REGIONS = ["north", "south", "east", "west"]
PERIODS = ["2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]
METRICS = ["sales", "returns", "signups", "refunds"]

SHIFTED_REGIONS = ["central", "overseas"]
SHIFTED_PERIODS = ["2027-Q1", "2027-Q2", "2027-Q3"]


# Filter + aggregate + rank helpers, shared by the tools and the ground truth.
def _filter(
    records: list[dict[str, Any]], region: str, period: str
) -> list[dict[str, Any]]:
    return [r for r in records if r["region"] == region and r["period"] == period]


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, int] = {}
    grand_total = 0
    for record in records:
        value = int(record["value"])
        totals[record["metric"]] = totals.get(record["metric"], 0) + value
        grand_total += value
    return {"totals": totals, "record_count": len(records), "grand_total": grand_total}


def _top_metric(totals: dict[str, int]) -> str:
    return min(totals, key=lambda metric: (-totals[metric], metric))


# Mock tools an agent could call; each pure.
def fetch_records(request: dict[str, Any]) -> dict[str, Any]:
    return {"records": request["records"]}


def filter_records(
    records: list[dict[str, Any]], region: str, period: str
) -> dict[str, Any]:
    return {"records": _filter(records, region, period)}


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    return _aggregate(records)


def rank_metrics(totals: dict[str, int]) -> dict[str, Any]:
    return {"top_metric": _top_metric(totals)}


def format_report(
    report_id: str, totals: dict[str, int], grand_total: int
) -> dict[str, Any]:
    return {"report": f"{report_id}: {grand_total} across {len(totals)} metrics"}


def _check(task: WorkloadTask, final_output: dict[str, Any]) -> bool:
    return all(final_output.get(key) == value for key, value in task.expected.items())


class ReportWorkload:
    @property
    def domain(self) -> str:
        return "report"

    def generate(
        self, n: int, *, seed: int, shifted: bool = False
    ) -> list[WorkloadTask]:
        rng = random.Random(seed)
        prefix = "report-shift" if shifted else "report"
        tasks: list[WorkloadTask] = []
        for i in range(n):
            request = _build_request(rng, shifted=shifted, report_index=i, seed=seed)
            matching = _filter(request["records"], request["region"], request["period"])
            agg = _aggregate(matching)
            tasks.append(
                WorkloadTask(
                    task_id=f"{prefix}-{seed}-{i}",
                    task_input=request,
                    expected={
                        "report_id": request["report_id"],
                        "totals": agg["totals"],
                        "record_count": agg["record_count"],
                        "grand_total": agg["grand_total"],
                        "top_metric": _top_metric(agg["totals"]),
                    },
                )
            )
        return tasks

    def tools(self) -> list[MockTool]:
        return [
            MockTool(name="fetch_records", fn=fetch_records),
            MockTool(name="filter_records", fn=filter_records),
            MockTool(name="aggregate", fn=aggregate),
            MockTool(name="rank_metrics", fn=rank_metrics),
            MockTool(name="format_report", fn=format_report),
        ]

    def checker(self) -> GroundTruthChecker:
        return _check


# One report request: matching records for chosen metrics plus non-matching noise.
def _build_request(
    rng: random.Random, *, shifted: bool, report_index: int, seed: int
) -> dict[str, Any]:
    if shifted:
        regions, periods = SHIFTED_REGIONS, SHIFTED_PERIODS
        value_range = (1, 5000)
        per_metric = (2, 4)
        noise_range = (6, 10)
        metric_count = (2, 4)
    else:
        regions, periods = REGIONS, PERIODS
        value_range = (1, 500)
        per_metric = (1, 3)
        noise_range = (3, 6)
        metric_count = (1, 4)

    region = rng.choice(regions)
    period = rng.choice(periods)
    chosen_metrics = rng.sample(METRICS, rng.randint(*metric_count))

    records: list[dict[str, Any]] = []
    for metric in chosen_metrics:
        for _ in range(rng.randint(*per_metric)):
            records.append(
                {
                    "region": region,
                    "period": period,
                    "metric": metric,
                    "value": rng.randint(*value_range),
                }
            )

    for _ in range(rng.randint(*noise_range)):
        records.append(
            {
                "region": rng.choice(regions),
                "period": rng.choice(periods),
                "metric": rng.choice(METRICS),
                "value": rng.randint(*value_range),
            }
        )

    rng.shuffle(records)
    return {
        "report_id": f"RPT-{seed:03d}{report_index:03d}",
        "region": region,
        "period": period,
        "records": records,
    }
