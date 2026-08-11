from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class UserCache(BaseModel):
    __tablename__ = "autotask_user_cache"

    user_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    org_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    portal_org_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
