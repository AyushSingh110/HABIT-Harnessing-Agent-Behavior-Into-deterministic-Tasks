# Drift monitor: flag a stale habit when recent runs keep falling back to live.

from collections import deque


class DriftMonitor:
    def __init__(self, *, window: int, threshold: float) -> None:
        self._modes: deque[str] = deque(maxlen=window)
        self._threshold = threshold

    def record(self, mode: str) -> None:
        self._modes.append(mode)

    def is_drifting(self) -> bool:
        attempts = [m for m in self._modes if m in ("habit", "fallback")]
        if not attempts:
            return False
        fallbacks = sum(1 for m in attempts if m == "fallback")
        return fallbacks / len(attempts) > self._threshold
