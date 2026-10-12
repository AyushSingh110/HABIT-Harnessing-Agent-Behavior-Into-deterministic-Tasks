# Value-envelope guard: learn each numeric field's range and flag out-of-range values.

from dataclasses import dataclass
from typing import Any

from habit.schemas import Trajectory


@dataclass(frozen=True)
class ValueEnvelope:
    lo: float
    hi: float


def _numeric_fields(result: dict[str, Any]) -> list[tuple[str, float]]:
    return [
        (field, float(value))
        for field, value in result.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]


def learn_envelopes(
    trajectories: list[Trajectory],
) -> dict[tuple[str, str], ValueEnvelope]:
    bounds: dict[tuple[str, str], tuple[float, float]] = {}
    for trajectory in trajectories:
        for step in trajectory.steps:
            if step.tool_call is None or not isinstance(step.tool_call.result, dict):
                continue
            for field, value in _numeric_fields(step.tool_call.result):
                key = (step.tool_call.tool_name, field)
                lo, hi = bounds.get(key, (value, value))
                bounds[key] = (min(lo, value), max(hi, value))
    return {key: ValueEnvelope(lo=lo, hi=hi) for key, (lo, hi) in bounds.items()}


class ValueGuard:
    def __init__(
        self, envelopes: dict[tuple[str, str], ValueEnvelope], *, tolerance: float
    ) -> None:
        self._envelopes = envelopes
        self._tolerance = tolerance

    def is_anomalous(self, tool_name: str, result: dict[str, Any]) -> bool:
        for field, value in _numeric_fields(result):
            envelope = self._envelopes.get((tool_name, field))
            if envelope is None:
                continue
            span = envelope.hi - envelope.lo
            scale = span if span > 0 else (abs(envelope.lo) if envelope.lo else 1.0)
            margin = self._tolerance * scale
            if value < envelope.lo - margin or value > envelope.hi + margin:
                return True
        return False
