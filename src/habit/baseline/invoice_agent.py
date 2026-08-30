# Authored invoice baseline: fixed workflow recording faithful per-step context reads.

from datetime import datetime, timezone

from habit.baseline.model import LargeModel
from habit.baseline.trace import BaselineTrace
from habit.interfaces import TrajectoryStore
from habit.recorder import TrajectoryRecorder
from habit.schemas import ContextKind, Trajectory
from habit.workloads import InvoiceWorkload, MockTool, WorkloadTask


def run_invoice_baseline(
    task: WorkloadTask,
    *,
    model: LargeModel,
    store: TrajectoryStore,
    tools: dict[str, MockTool],
    trajectory_id: str,
) -> Trajectory:
    invoice = task.task_input
    run = TrajectoryRecorder(store).start_run(
        trajectory_id=trajectory_id,
        domain="invoice",
        task_type="process_invoice",
        task_input=invoice,
        metadata={"agent": "baseline"},
        started_at=datetime.now(timezone.utc),
    )
    trace = BaselineTrace(run, model, tools, trajectory_id)
    trace.add_input("invoice", ContextKind.DOCUMENT)

    trace.llm(["invoice"])
    header = trace.tool("extract_header", {"invoice": invoice}, "header", ["invoice"])
    trace.llm(["invoice"])
    line_items = trace.tool(
        "extract_line_items", {"invoice": invoice}, "line_items", ["invoice"]
    )
    trace.llm(["invoice"])
    validation = trace.tool(
        "validate_totals", {"invoice": invoice}, "validation", ["invoice"]
    )
    trace.llm(["header"])
    vendor_lookup = trace.tool(
        "lookup_vendor", {"vendor": header["vendor"]}, "vendor_lookup", ["header"]
    )
    trace.llm(["header", "line_items", "validation", "vendor_lookup"])

    final_output = {
        "invoice_id": header["invoice_id"],
        "vendor": header["vendor"],
        "total": header["total"],
        "line_item_count": line_items["count"],
        "totals_valid": validation["totals_valid"],
        "vendor_known": vendor_lookup["vendor_known"],
    }
    match = InvoiceWorkload().checker()(task, final_output)
    return run.finish(
        success=True,
        final_output=final_output,
        ended_at=datetime.now(timezone.utc),
        ground_truth_match=match,
    )
