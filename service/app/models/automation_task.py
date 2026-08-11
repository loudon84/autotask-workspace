from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AutomationTask(BaseModel):
    __tablename__ = "automation_tasks"
    __table_args__ = (
        Index("ix_automation_tasks_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("ix_automation_tasks_tenant_portal", "tenant_id", "portal_account_id"),
        Index("ix_automation_tasks_tenant_binding", "tenant_id", "workflow_binding_id"),
        Index("ix_automation_tasks_source_task_id", "source_task_id"),
        Index("ix_automation_tasks_source_run_id", "source_run_id"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    task_type: Mapped[str] = mapped_column(String(128), nullable=False)
    portal_account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_binding_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_entity_code: Mapped[str] = mapped_column(String(128), nullable=False)
    erp_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)
    input: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
