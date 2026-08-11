from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RpaWorker(BaseModel):
    __tablename__ = "rpa_workers"
    __table_args__ = (
        Index("ix_rpa_workers_status_heartbeat", "status", "last_heartbeat_at"),
    )

    worker_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    worker_type: Mapped[str] = mapped_column(String(32), nullable=False)
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ONLINE", nullable=False)
    capabilities: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
