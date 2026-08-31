# Paging simulation: window token load per step for naive keep-all vs policy keep-live.

from dataclasses import dataclass

from habit.context.policy import ContextPolicy


@dataclass(frozen=True)
class PagingTrace:
    naive_tokens_per_step: tuple[int, ...]
    policy_tokens_per_step: tuple[int, ...]
    naive_peak: int
    policy_peak: int


def simulate_paging(policy: ContextPolicy, sizes: dict[str, int]) -> PagingTrace:
    naive_tokens: list[int] = []
    policy_tokens: list[int] = []
    for step in policy.steps:
        present = set(step.live) | set(step.evictable)
        for item in present:
            if item not in sizes:
                raise ValueError(f"size missing for context item: {item}")
        naive_tokens.append(sum(sizes[item] for item in present))
        policy_tokens.append(sum(sizes[item] for item in step.live))
    return PagingTrace(
        naive_tokens_per_step=tuple(naive_tokens),
        policy_tokens_per_step=tuple(policy_tokens),
        naive_peak=max(naive_tokens, default=0),
        policy_peak=max(policy_tokens, default=0),
    )


def survives(trace: PagingTrace, budget: int) -> tuple[bool, bool]:
    return (trace.naive_peak <= budget, trace.policy_peak <= budget)
