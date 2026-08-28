"""门户创建人/归属人显示名：id 旁加 name 字段。

Revision ID: c1d8e4f90a62
Revises: b8c9d0e12f51
Create Date: 2026-08-28 15:40:00

列表展示读本表，不再为显示去调下属接口。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d8e4f90a62"
down_revision: str | None = "b8c9d0e12f51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_accounts",
        sa.Column(
            "owner_user_name",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "portal_accounts",
        sa.Column(
            "created_by_name",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE portal_accounts AS p
            SET owner_user_name = c.name
            FROM autotask_user_cache AS c
            WHERE c.user_id = COALESCE(p.owner_user_id, p.created_by)
              AND c.deleted_at IS NULL
              AND (p.owner_user_name IS NULL OR p.owner_user_name = '')
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE portal_accounts AS p
            SET created_by_name = c.name
            FROM autotask_user_cache AS c
            WHERE c.user_id = p.created_by
              AND c.deleted_at IS NULL
              AND (p.created_by_name IS NULL OR p.created_by_name = '')
            """
        )
    )


def downgrade() -> None:
    op.drop_column("portal_accounts", "created_by_name")
    op.drop_column("portal_accounts", "owner_user_name")
