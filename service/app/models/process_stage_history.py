from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ProcessStageHistory(BaseModel):
    __tablename__ = "process_stage_history"
    __table_args__ = (
        Index("ix_process_stage_history_instance", "instance_id", "created_at"),
    )

    instance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
