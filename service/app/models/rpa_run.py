from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RpaRun(BaseModel):
    __tablename__ = "rpa_runs"
    __table_args__ = (
        Index("ix_rpa_runs_task_status", "task_id", "status"),
    )

    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rpa_flow_id: Mapped[str] = mapped_column(String(255), nullable=False)
    rpa_worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False)
    current_step_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
