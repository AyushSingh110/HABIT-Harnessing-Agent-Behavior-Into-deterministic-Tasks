# Router: select a usable habit for a task, or fall back to the live agent.

from dataclasses import dataclass
from typing import Any

from habit.compiler import CompiledHabit, HabitPlan, InputField, Source


def _input_field_keys(sources: list[Source]) -> set[str]:
    return {source.key for source in sources if isinstance(source, InputField)}


@dataclass(frozen=True)
class Router:
    habits: dict[str, HabitPlan]

    def route(self, domain: str, task_input: dict[str, Any]) -> HabitPlan | None:
        plan = self.habits.get(domain)
        if plan is None:
            return None
        needed: set[str] = set()
        for step in plan.steps:
            needed |= _input_field_keys(list(step.arg_sources.values()))
        needed |= _input_field_keys(list(plan.output_assembly.values()))
        if not needed <= task_input.keys():
            return None
        return plan


def build_router(compiled: dict[str, CompiledHabit]) -> Router:
    return Router(habits={domain: h.plan for domain, h in compiled.items() if h.usable})
