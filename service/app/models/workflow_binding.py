from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WorkflowBinding(BaseModel):
    __tablename__ = "workflow_bindings"
    __table_args__ = (
        Index("ix_workflow_bindings_portal_account_id", "portal_account_id"),
        Index("ix_workflow_bindings_workflow_template_id", "workflow_template_id"),
    )

    portal_account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_template_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_template_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rpa_engine_type: Mapped[str] = mapped_column(String(64), default="PLAYWRIGHT_CDP", nullable=False)
    rpa_flow_id: Mapped[str] = mapped_column(String(255), nullable=False)
    rpa_flow_version: Mapped[str] = mapped_column(String(64), default="1.0.0", nullable=False)
    rpa_flow_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    flow_checksum_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ENABLED", nullable=False)
    config: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
