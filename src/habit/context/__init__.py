# Layer 3 context: induce per-step context policies from recorded access patterns.

from habit.context.paging import PagingTrace, simulate_paging, survives
from habit.context.policy import (
    ContextPolicy,
    StepContextPolicy,
    induce_context_policy,
    working_set_sizes,
)
from habit.context.validation import (
    ContextValidation,
    ValidatedContextPolicy,
    induce_and_validate_policy,
    validate_context_policy,
)

__all__ = [
    "StepContextPolicy",
    "ContextPolicy",
    "induce_context_policy",
    "working_set_sizes",
    "PagingTrace",
    "simulate_paging",
    "survives",
    "ContextValidation",
    "ValidatedContextPolicy",
    "validate_context_policy",
    "induce_and_validate_policy",
]
