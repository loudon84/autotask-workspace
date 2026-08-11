from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HumanAction(BaseModel):
    __tablename__ = "human_actions"
    __table_args__ = (
        Index("ix_human_actions_status_created", "status", "created_at"),
        Index("ix_human_actions_task_id", "task_id"),
        Index(
            "uq_human_actions_run_id_active",
            "run_id",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND run_id IS NOT NULL AND status IN ('PENDING', 'OPENED')"
            ),
        ),
    )

    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    target_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    payload: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    opened_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
