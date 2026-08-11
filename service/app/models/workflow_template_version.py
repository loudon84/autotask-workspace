from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WorkflowTemplateVersion(BaseModel):
    __tablename__ = "workflow_template_versions"
    __table_args__ = (
        Index("ix_workflow_template_versions_template_id", "template_id"),
    )

    template_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
