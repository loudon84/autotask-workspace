from sqlalchemy import Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ProcessInstance(BaseModel):
    __tablename__ = "process_instances"
    __table_args__ = (
        UniqueConstraint(
            "portal_account_id",
            "process_code",
            "biz_key",
            name="uq_process_instances_portal_code_biz",
        ),
        Index("ix_process_instances_tenant_status", "tenant_id", "status"),
        Index("ix_process_instances_tenant_stage", "tenant_id", "stage"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    process_code: Mapped[str] = mapped_column(String(128), nullable=False)
    biz_key: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    portal_account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    line_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
