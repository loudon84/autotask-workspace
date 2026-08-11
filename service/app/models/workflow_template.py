from sqlalchemy import Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WorkflowTemplate(BaseModel):
    __tablename__ = "workflow_templates"
    __table_args__ = (
        Index(
            "uq_workflow_templates_tenant_code",
            "tenant_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_workflow_templates_tenant_id", "tenant_id"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)
    version: Mapped[str] = mapped_column(String(64), default="1.0.0", nullable=False)
    input_schema: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    business_steps: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
