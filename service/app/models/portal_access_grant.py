from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PortalAccessGrant(BaseModel):
    __tablename__ = "portal_access_grants"
    __table_args__ = (
        Index("ix_portal_access_grants_portal_account_id", "portal_account_id"),
        Index("ix_portal_access_grants_subject", "subject_type", "subject_id"),
    )

    portal_account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    permissions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    granted_by: Mapped[str] = mapped_column(String(36), nullable=False)
    granted_at: Mapped[str] = mapped_column(String(64), nullable=False)
