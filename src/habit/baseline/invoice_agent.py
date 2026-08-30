# Authored invoice baseline: fixed workflow recording faithful per-step context reads.

from datetime import datetime, timezone
from typing import Any

from habit.baseline.model import LargeModel
from habit.interfaces import TrajectoryStore
from habit.recorder import TrajectoryRecorder
from habit.schemas import ContextItem, ContextKind, Trajectory
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

    available: list[str] = ["invoice"]
    run.add_context_item(
        ContextItem(
            item_id="invoice",
            kind=ContextKind.DOCUMENT,
            produced_by_step=None,
            content_hash=None,
            size_tokens=None,
        )
    )
    step = 0

    def llm(reads: list[str]) -> None:
        nonlocal step
        response = model.complete(f"invoice step {step}")
        now = datetime.now(timezone.utc)
        run.record_llm_call(
            provider=model.provider,
            model=model.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            context_available=list(available),
            context_reads=reads,
            started_at=now,
            ended_at=now,
        )
        step += 1

    def tool(
        name: str, kwargs: dict[str, Any], produced_id: str, reads: list[str]
    ) -> Any:
        nonlocal step
        result = tools[name](**kwargs)
        now = datetime.now(timezone.utc)
        run.record_tool_call(
            tool_name=name,
            call_id=f"{trajectory_id}-s{step}",
            arguments=kwargs,
            result=result,
            error=None,
            context_available=list(available),
            context_reads=reads,
            started_at=now,
            ended_at=now,
        )
        run.add_context_item(
            ContextItem(
                item_id=produced_id,
                kind=ContextKind.TOOL_RESULT,
                produced_by_step=step,
                content_hash=None,
                size_tokens=None,
            )
        )
        available.append(produced_id)
        step += 1
        return result

    llm(["invoice"])
    header = tool("extract_header", {"invoice": invoice}, "header", ["invoice"])
    llm(["invoice"])
    line_items = tool(
        "extract_line_items", {"invoice": invoice}, "line_items", ["invoice"]
    )
    llm(["invoice"])
    validation = tool(
        "validate_totals", {"invoice": invoice}, "validation", ["invoice"]
    )
    llm(["header"])
    vendor_lookup = tool(
        "lookup_vendor", {"vendor": header["vendor"]}, "vendor_lookup", ["header"]
    )
    llm(["header", "line_items", "validation", "vendor_lookup"])

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
