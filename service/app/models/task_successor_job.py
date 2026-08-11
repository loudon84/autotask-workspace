from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TaskSuccessorJob(BaseModel):
    __tablename__ = "task_successor_jobs"
    __table_args__ = (
        Index(
            "uq_task_successor_jobs_source_run_target",
            "source_run_id",
            "target_workflow_binding_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_task_successor_jobs_ready",
            "status",
            "next_attempt_at",
        ),
        Index(
            "ix_task_successor_jobs_tenant_source_task",
            "tenant_id",
            "source_task_id",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_workflow_binding_id: Mapped[str] = mapped_column(String(36), nullable=False)
    input_mapper: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    successor_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
