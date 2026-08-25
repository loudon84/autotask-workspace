from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SchedulerJob(BaseModel):
    __tablename__ = "scheduler_jobs"
    __table_args__ = (
        Index(
            "uq_scheduler_jobs_binding_id",
            "binding_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_scheduler_jobs_portal_account_id", "portal_account_id"),
        Index("ix_scheduler_jobs_enabled", "enabled"),
    )

    binding_id: Mapped[str] = mapped_column(String(36), nullable=False)
    portal_account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cron: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
