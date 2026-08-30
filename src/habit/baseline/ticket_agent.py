# Authored ticket baseline: fixed triage workflow with faithful per-step reads.

from datetime import datetime, timezone

from habit.baseline.model import LargeModel
from habit.baseline.trace import BaselineTrace
from habit.interfaces import TrajectoryStore
from habit.recorder import TrajectoryRecorder
from habit.schemas import ContextKind, Trajectory
from habit.workloads import MockTool, TicketWorkload, WorkloadTask


def run_ticket_baseline(
    task: WorkloadTask,
    *,
    model: LargeModel,
    store: TrajectoryStore,
    tools: dict[str, MockTool],
    trajectory_id: str,
) -> Trajectory:
    ticket = task.task_input
    run = TrajectoryRecorder(store).start_run(
        trajectory_id=trajectory_id,
        domain="ticket",
        task_type="triage_ticket",
        task_input=ticket,
        metadata={"agent": "baseline"},
        started_at=datetime.now(timezone.utc),
    )
    trace = BaselineTrace(run, model, tools, trajectory_id)
    trace.add_input("message", ContextKind.MESSAGE)
    trace.add_input("customer_id", ContextKind.DOCUMENT)
    trace.add_input("ticket_meta", ContextKind.DOCUMENT)

    trace.llm(["message"])
    classification = trace.tool(
        "classify_ticket", {"message": ticket["message"]}, "category", ["message"]
    )
    category = classification["category"]
    trace.llm(["customer_id"])
    customer = trace.tool(
        "lookup_customer",
        {"customer_id": ticket["customer_id"]},
        "customer",
        ["customer_id"],
    )
    trace.llm(["category"])
    priority = trace.tool(
        "decide_priority", {"category": category}, "priority", ["category"]
    )
    trace.llm(["category"])
    routing = trace.tool(
        "route_ticket", {"category": category}, "routing", ["category"]
    )
    trace.llm(["ticket_meta"])
    trace.tool(
        "close_ticket", {"ticket_id": ticket["ticket_id"]}, "closure", ["ticket_meta"]
    )
    trace.llm(["category", "customer", "priority", "routing"])

    final_output = {
        "ticket_id": ticket["ticket_id"],
        "category": category,
        "team": routing["team"],
        "priority": priority["priority"],
        "customer_known": customer["customer_known"],
    }
    match = TicketWorkload().checker()(task, final_output)
    return run.finish(
        success=True,
        final_output=final_output,
        ended_at=datetime.now(timezone.utc),
        ground_truth_match=match,
    )
