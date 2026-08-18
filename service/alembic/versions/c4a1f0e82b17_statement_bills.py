"""天地伟业对账单头表 statement_bills。

Revision ID: c4a1f0e82b17
Revises: b2e8a4c91f30
Create Date: 2026-08-17 19:10:00

说明：本迁移为 dormant DDL，默认不在本会话执行；需用户明确授权后再 alembic upgrade。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4a1f0e82b17"
down_revision: str | None = "b2e8a4c91f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "statement_bills",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("process_instance_id", sa.String(length=36), nullable=False),
        sa.Column("portal_account_id", sa.String(length=36), nullable=False),
        sa.Column("check_date", sa.Date(), nullable=False),
        sa.Column("check_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("check_status", sa.String(length=16), nullable=False, server_default="UNCHECKED"),
        sa.Column("invoice_status", sa.String(length=16), nullable=False, server_default="NOT_UPLOADED"),
        sa.Column("invoice_no", sa.String(length=256), nullable=True),
        sa.Column("invoice_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("sdms_check_head_id", sa.String(length=32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "check_date", "check_amount",
            name="uq_statement_bills_tenant_date_amount",
        ),
        sa.Index("ix_statement_bills_tenant_check_status", "tenant_id", "check_status"),
    )
    op.create_index("ix_statement_bills_process_instance_id", "statement_bills", ["process_instance_id"])
    op.create_index("ix_statement_bills_deleted_at", "statement_bills", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_statement_bills_deleted_at", table_name="statement_bills")
    op.drop_index("ix_statement_bills_process_instance_id", table_name="statement_bills")
    op.drop_table("statement_bills")
