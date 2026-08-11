from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TaskMessage(BaseModel):
    __tablename__ = "task_messages"
    __table_args__ = (
        Index("ix_task_messages_task_id", "task_id"),
    )

    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
