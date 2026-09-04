from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RegionCodeMap(BaseModel):
    """WMS region code to SRM display name, keyed by hardcoded category."""

    __tablename__ = "region_code_maps"
    __table_args__ = (
        Index(
            "uq_region_code_maps_active",
            "tenant_id",
            "category",
            "region_code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_region_code_maps_tenant_category", "tenant_id", "category"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    region_code: Mapped[str] = mapped_column(String(64), nullable=False)
    srm_display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_by_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
