# SQLAlchemy 2.x Declarative model for trajectory persistence.

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TrajectoryRow(Base):
    __tablename__ = "trajectories"

    trajectory_id: Mapped[str] = mapped_column(String, primary_key=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    task_type: Mapped[str] = mapped_column(String)
    success: Mapped[bool] = mapped_column(Boolean, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
