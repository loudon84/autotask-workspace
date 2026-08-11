from sqlalchemy import BigInteger, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Artifact(BaseModel):
    __tablename__ = "artifacts"
    __table_args__ = (
        Index("ix_artifacts_task_run", "task_id", "run_id"),
        Index("ix_artifacts_tenant_id", "tenant_id"),
        Index(
            "uq_artifacts_run_id_storage_key",
            "run_id",
            "storage_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND run_id IS NOT NULL"),
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
