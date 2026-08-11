from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WorkerLease(BaseModel):
    __tablename__ = "worker_leases"
    __table_args__ = (
        Index("ix_worker_leases_task_expires", "task_id", "lease_expires_at"),
        Index("ix_worker_leases_worker_id", "worker_id"),
    )

    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    lease_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
