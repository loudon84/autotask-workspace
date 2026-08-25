"""门户增加我方业务实体、OU。

Revision ID: d8f3a1b62c90
Revises: c4a1f0e82b17
Create Date: 2026-08-19 15:20:00

说明：本迁移为 dormant DDL，默认不在本会话执行；需用户明确授权后再 alembic upgrade。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8f3a1b62c90"
down_revision: str | None = "c4a1f0e82b17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_accounts",
        sa.Column("business_entity", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "portal_accounts",
        sa.Column("ou", sa.String(length=64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("portal_accounts", "ou")
    op.drop_column("portal_accounts", "business_entity")
