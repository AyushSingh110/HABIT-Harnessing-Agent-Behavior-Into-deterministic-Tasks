# Long-horizon study: naive keep-all context overflows while the policy stays bounded.

from dataclasses import dataclass
from datetime import datetime, timezone

from habit.compiler import cluster_trajectories
from habit.context import induce_and_validate_policy, simulate_paging, survives
from habit.schemas import (
    ContextItem,
    ContextKind,
    Outcome,
    Step,
    StepType,
    ToolCall,
    Trajectory,
    schema_fingerprint,
)

T0 = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def generate_long_horizon(n_steps: int, *, count: int, seed: int) -> list[Trajectory]:
    trajectories: list[Trajectory] = []
    for t in range(count):
        context_items = [
            ContextItem(
                item_id="goal",
                kind=ContextKind.DOCUMENT,
                produced_by_step=None,
                content_hash=None,
                size_tokens=None,
            )
        ]
        steps: list[Step] = []
        for k in range(n_steps):
            context_items.append(
                ContextItem(
                    item_id=f"r{k}",
                    kind=ContextKind.TOOL_RESULT,
                    produced_by_step=k,
                    content_hash=None,
                    size_tokens=None,
                )
            )
            result = {"i": k}
            available = ["goal"] + [f"r{j}" for j in range(k)]
            reads = ["goal"] if k == 0 else ["goal", f"r{k - 1}"]
            steps.append(
                Step(
                    step_index=k,
                    step_type=StepType.TOOL_CALL,
                    llm_call=None,
                    tool_call=ToolCall(
                        tool_name="work",
                        call_id=f"c{k}",
                        arguments={"prev": k - 1},
                        result=result,
                        error=None,
                    ),
                    tool_result_schema_fingerprint=schema_fingerprint(result),
                    context_available=available,
                    context_reads=reads,
                    started_at=T0,
                    ended_at=T0,
                )
            )
        trajectories.append(
            Trajectory(
                trajectory_id=f"long-{seed}-{t}",
                domain="long_horizon",
                task_type="chain",
                task_input={},
                context_items=context_items,
                steps=steps,
                outcome=Outcome(
                    success=True,
                    final_output={"steps": n_steps},
                    error=None,
                    ground_truth_match=True,
                ),
                started_at=T0,
                ended_at=T0,
                metadata={},
            )
        )
    return trajectories


@dataclass(frozen=True)
class LongHorizonResult:
    n_steps: int
    naive_peak: int
    policy_peak: int
    token_savings_pct: float
    safe: bool
    budget: int
    naive_survives: bool
    policy_survives: bool


def run_long_horizon_study(
    *,
    n_steps: int = 50,
    count: int = 8,
    seed: int = 0,
    item_size: int = 1,
    budget: int | None = None,
) -> LongHorizonResult:
    trajectories = generate_long_horizon(n_steps, count=count, seed=seed)
    cluster = cluster_trajectories(trajectories)[0]
    by_id = {t.trajectory_id: t for t in trajectories}
    vp = induce_and_validate_policy(cluster, by_id)

    items: set[str] = set()
    for step in vp.policy.steps:
        items |= set(step.live) | set(step.evictable)
    sizes = {item: item_size for item in items}

    trace = simulate_paging(vp.policy, sizes)
    resolved_budget = trace.policy_peak if budget is None else budget
    naive_survives, policy_survives = survives(trace, resolved_budget)
    return LongHorizonResult(
        n_steps=n_steps,
        naive_peak=trace.naive_peak,
        policy_peak=trace.policy_peak,
        token_savings_pct=1 - trace.policy_peak / trace.naive_peak,
        safe=vp.safe,
        budget=resolved_budget,
        naive_survives=naive_survives,
        policy_survives=policy_survives,
    )
