from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RegionCodeMap(BaseModel):
    """地区编号宽表：code 共用，默认名兜底，SRM 专列可空（空=用默认名）。

    新 SRM 需要原产地时才加对应 name 列（如 tiandy_name），随该 SRM 的
    接入开发一起迁移；不加列的 SRM 一律读 default_name。
    """

    __tablename__ = "region_code_maps"
    __table_args__ = (
        Index(
            "uq_region_code_maps_active",
            "tenant_id",
            "region_code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_region_code_maps_tenant", "tenant_id"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    region_code: Mapped[str] = mapped_column(String(64), nullable=False)
    default_name: Mapped[str] = mapped_column(String(128), nullable=False)
    boe_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_by_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
