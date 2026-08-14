"""流程行表补齐 SRM 附件明细列。

Revision ID: b2e8a4c91f30
Revises: 9a3f2c71b5d4
Create Date: 2026-08-13 15:40:00

说明：本迁移为 dormant DDL，默认不在本会话执行；需用户明确授权后再 alembic upgrade。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2e8a4c91f30"
down_revision: str | None = "9a3f2c71b5d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("process_line_items", sa.Column("material_status", sa.String(length=128), nullable=True))
    op.add_column("process_line_items", sa.Column("internal_code", sa.String(length=128), nullable=True))
    op.add_column("process_line_items", sa.Column("unit_selling_price", sa.String(length=64), nullable=True))
    op.add_column("process_line_items", sa.Column("tax_included_amount", sa.String(length=64), nullable=True))
    op.add_column("process_line_items", sa.Column("meets_lead_time", sa.String(length=64), nullable=True))
    op.add_column("process_line_items", sa.Column("supplier_delivery_date", sa.String(length=32), nullable=True))
    op.add_column("process_line_items", sa.Column("outstanding_quantity", sa.String(length=64), nullable=True))
    op.add_column("process_line_items", sa.Column("remarks", sa.Text(), nullable=True))
    op.add_column("process_line_items", sa.Column("direct_shipment_remarks", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("process_line_items", "direct_shipment_remarks")
    op.drop_column("process_line_items", "remarks")
    op.drop_column("process_line_items", "outstanding_quantity")
    op.drop_column("process_line_items", "supplier_delivery_date")
    op.drop_column("process_line_items", "meets_lead_time")
    op.drop_column("process_line_items", "tax_included_amount")
    op.drop_column("process_line_items", "unit_selling_price")
    op.drop_column("process_line_items", "internal_code")
    op.drop_column("process_line_items", "material_status")
