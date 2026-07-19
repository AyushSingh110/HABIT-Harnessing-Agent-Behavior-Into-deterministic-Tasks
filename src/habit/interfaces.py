# Cross-layer storage contract. Backend-agnostic; the real implementation ships in T4.

from typing import Protocol, runtime_checkable

from habit.schemas import Trajectory


@runtime_checkable
class TrajectoryStore(Protocol):
    def save(self, trajectory: Trajectory) -> None:
        """Persist one trajectory; raise ValueError if trajectory_id already exists."""
        ...

    def get(self, trajectory_id: str) -> Trajectory | None:
        """Return the trajectory with this id, or None if absent."""
        ...

    def query(
        self,
        *,
        domain: str | None = None,
        task_type: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
    ) -> list[Trajectory]:
        """Matches ALL filters (AND), started_at ascending, capped by limit."""
        ...

    def count(
        self,
        *,
        domain: str | None = None,
        task_type: str | None = None,
        success: bool | None = None,
    ) -> int:
        """Number of trajectories matching ALL filters (same semantics as query)."""
        ...
