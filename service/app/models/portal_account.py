from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PortalAccount(BaseModel):
    __tablename__ = "portal_accounts"
    __table_args__ = (
        Index(
            "uq_portal_accounts_tenant_portal_name",
            "tenant_id",
            "portal_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_portal_accounts_tenant_id", "tenant_id"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_entity_code: Mapped[str] = mapped_column(String(128), nullable=False)
    erp_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_entity: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    ou: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="TIANDI", nullable=False)
    portal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    portal_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    login_account: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_open_mode: Mapped[str] = mapped_column(String(32), default="webcontents", nullable=False)
    client_session_partition: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    rpa_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ENABLED", nullable=False)
    owner_dept_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    owner_user_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
