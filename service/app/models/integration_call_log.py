from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IntegrationCallLog(BaseModel):
    """v5.4 接口调用日志：一次主动 HTTP 一行，用 task_id 关联。"""

    __tablename__ = "integration_call_logs"
    __table_args__ = (
        Index("ix_integration_call_logs_task_created", "task_id", "created_at"),
        Index("ix_integration_call_logs_run_id", "run_id"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    system: Mapped[str] = mapped_column(String(32), nullable=False)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    response_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
