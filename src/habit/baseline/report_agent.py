# Authored report baseline: fixed fetch/filter/aggregate/rank/format workflow.

from datetime import datetime, timezone

from habit.baseline.model import LargeModel
from habit.baseline.trace import BaselineTrace
from habit.interfaces import TrajectoryStore
from habit.recorder import TrajectoryRecorder
from habit.schemas import ContextKind, Trajectory
from habit.workloads import MockTool, ReportWorkload, WorkloadTask


def run_report_baseline(
    task: WorkloadTask,
    *,
    model: LargeModel,
    store: TrajectoryStore,
    tools: dict[str, MockTool],
    trajectory_id: str,
) -> Trajectory:
    request = task.task_input
    run = TrajectoryRecorder(store).start_run(
        trajectory_id=trajectory_id,
        domain="report",
        task_type="generate_report",
        task_input=request,
        metadata={"agent": "baseline"},
        started_at=datetime.now(timezone.utc),
    )
    trace = BaselineTrace(run, model, tools, trajectory_id)
    trace.add_input("request", ContextKind.DOCUMENT)

    trace.llm(["request"])
    raw = trace.tool("fetch_records", {"request": request}, "raw_records", ["request"])
    trace.llm(["raw_records"])
    filtered = trace.tool(
        "filter_records",
        {
            "records": raw["records"],
            "region": request["region"],
            "period": request["period"],
        },
        "filtered",
        ["request", "raw_records"],
    )
    trace.llm(["filtered"])
    aggregate = trace.tool(
        "aggregate", {"records": filtered["records"]}, "aggregate", ["filtered"]
    )
    trace.llm(["aggregate"])
    ranking = trace.tool(
        "rank_metrics", {"totals": aggregate["totals"]}, "ranking", ["aggregate"]
    )
    trace.llm(["aggregate", "request"])
    trace.tool(
        "format_report",
        {
            "report_id": request["report_id"],
            "totals": aggregate["totals"],
            "grand_total": aggregate["grand_total"],
        },
        "report",
        ["aggregate", "request"],
    )
    trace.llm(["aggregate", "ranking", "request"])

    final_output = {
        "report_id": request["report_id"],
        "totals": aggregate["totals"],
        "record_count": aggregate["record_count"],
        "grand_total": aggregate["grand_total"],
        "top_metric": ranking["top_metric"],
    }
    match = ReportWorkload().checker()(task, final_output)
    return run.finish(
        success=True,
        final_output=final_output,
        ended_at=datetime.now(timezone.utc),
        ground_truth_match=match,
    )
