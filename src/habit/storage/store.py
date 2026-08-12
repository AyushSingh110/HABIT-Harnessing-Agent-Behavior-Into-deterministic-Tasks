# SQLAlchemy 2.x implementation of the TrajectoryStore protocol.

import os
from datetime import timezone

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from habit.schemas import Trajectory
from habit.storage.models import Base, TrajectoryRow


def engine_from_env() -> Engine:
    url = os.environ.get("DATABASE_URL", "sqlite:///habit.db")
    return create_engine(url)


class SqlAlchemyTrajectoryStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        Base.metadata.create_all(engine)

    def save(self, trajectory: Trajectory) -> None:
        if self.get(trajectory.trajectory_id) is not None:
            msg = f"trajectory_id already exists: {trajectory.trajectory_id}"
            raise ValueError(msg)

        started_at_naive = trajectory.started_at.astimezone(timezone.utc).replace(
            tzinfo=None
        )
        row = TrajectoryRow(
            trajectory_id=trajectory.trajectory_id,
            domain=trajectory.domain,
            task_type=trajectory.task_type,
            success=trajectory.outcome.success,
            started_at=started_at_naive,
            payload=trajectory.model_dump(mode="json"),
        )

        with Session(self._engine) as session:
            session.add(row)
            session.commit()

    def get(self, trajectory_id: str) -> Trajectory | None:
        with Session(self._engine) as session:
            row = session.get(TrajectoryRow, trajectory_id)
            if row is None:
                return None
            return Trajectory.model_validate(row.payload)

    def query(
        self,
        *,
        domain: str | None = None,
        task_type: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
    ) -> list[Trajectory]:
        stmt = select(TrajectoryRow)
        if domain is not None:
            stmt = stmt.where(TrajectoryRow.domain == domain)
        if task_type is not None:
            stmt = stmt.where(TrajectoryRow.task_type == task_type)
        if success is not None:
            stmt = stmt.where(TrajectoryRow.success == success)

        stmt = stmt.order_by(
            TrajectoryRow.started_at.asc(), TrajectoryRow.trajectory_id.asc()
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        with Session(self._engine) as session:
            rows = session.scalars(stmt).all()
            return [Trajectory.model_validate(row.payload) for row in rows]

    def count(
        self,
        *,
        domain: str | None = None,
        task_type: str | None = None,
        success: bool | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(TrajectoryRow)
        if domain is not None:
            stmt = stmt.where(TrajectoryRow.domain == domain)
        if task_type is not None:
            stmt = stmt.where(TrajectoryRow.task_type == task_type)
        if success is not None:
            stmt = stmt.where(TrajectoryRow.success == success)

        with Session(self._engine) as session:
            result = session.scalar(stmt)
            return result if result is not None else 0
