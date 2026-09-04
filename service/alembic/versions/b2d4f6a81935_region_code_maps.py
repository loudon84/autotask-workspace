"""WMS 地区编号 → SRM 显示名。未授权不得在演示/正式库执行。

Revision ID: b2d4f6a81935
Revises: a1c3e5f70824
Create Date: 2026-09-03 16:50:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2d4f6a81935"
down_revision: str | None = "a1c3e5f70824"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "region_code_maps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("region_code", sa.String(length=64), nullable=False),
        sa.Column("srm_display_name", sa.String(length=128), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by_name", sa.String(length=255), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_region_code_maps_tenant_category",
        "region_code_maps",
        ["tenant_id", "category"],
    )
    op.create_index("ix_region_code_maps_deleted_at", "region_code_maps", ["deleted_at"])
    op.create_index(
        "uq_region_code_maps_active",
        "region_code_maps",
        ["tenant_id", "category", "region_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_region_code_maps_active", table_name="region_code_maps")
    op.drop_index("ix_region_code_maps_deleted_at", table_name="region_code_maps")
    op.drop_index("ix_region_code_maps_tenant_category", table_name="region_code_maps")
    op.drop_table("region_code_maps")
