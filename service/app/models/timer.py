from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[domain#SchedulerJob]]
class Timer(BaseModel):
    """独立定时器档案。没有门户、没有 Binding。"""

    __tablename__ = "timers"
    __table_args__ = (
        Index(
            "uq_timers_target",
            "target",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_timers_enabled", "enabled"),
    )

    target: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cron: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
