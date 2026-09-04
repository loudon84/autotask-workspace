from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

# 状态：RUNNING 到点已触发未结束；SUCCESS / FAILED / NO_LISTENER（无注册入口）
TIMER_RUN_RUNNING = "RUNNING"
TIMER_RUN_SUCCESS = "SUCCESS"
TIMER_RUN_FAILED = "FAILED"
TIMER_RUN_NO_LISTENER = "NO_LISTENER"


class TimerRun(BaseModel):
    """定时器一次到点执行的记录：何时触发、何时结束、结果如何。"""

    __tablename__ = "timer_runs"
    __table_args__ = (
        Index("ix_timer_runs_timer_id", "timer_id"),
        Index("ix_timer_runs_triggered_at", "triggered_at"),
    )

    timer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
