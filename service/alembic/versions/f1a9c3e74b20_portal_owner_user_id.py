"""门户归属人 owner_user_id，以及 user_cache 缓存的管人名单。

Revision ID: f1a9c3e74b20
Revises: e2b7c14a3d05
Create Date: 2026-08-24 09:30:00

已有门户回填 owner_user_id = created_by。
2026-08-24 用户授权后已执行 alembic upgrade 至本 revision。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a9c3e74b20"
down_revision: str | None = "e2b7c14a3d05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_accounts",
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE portal_accounts SET owner_user_id = created_by "
            "WHERE owner_user_id IS NULL AND created_by IS NOT NULL"
        )
    )
    op.create_index(
        "ix_portal_accounts_owner_user_id",
        "portal_accounts",
        ["owner_user_id"],
    )
    op.add_column(
        "autotask_user_cache",
        sa.Column("managed_user_ids", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("autotask_user_cache", "managed_user_ids")
    op.drop_index("ix_portal_accounts_owner_user_id", table_name="portal_accounts")
    op.drop_column("portal_accounts", "owner_user_id")
