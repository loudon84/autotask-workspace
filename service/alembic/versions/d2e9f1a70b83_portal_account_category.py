"""门户分类码：portal_accounts.category，现网回填 TIANDI。

Revision ID: d2e9f1a70b83
Revises: c1d8e4f90a62
Create Date: 2026-09-03 11:10:00

分类键值对写死在代码（TIANDI/BOE）；本列只存 code。未授权不得在演示/正式库执行。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e9f1a70b83"
down_revision: str | None = "c1d8e4f90a62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_accounts",
        sa.Column(
            "category",
            sa.String(length=32),
            nullable=True,
            server_default="TIANDI",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE portal_accounts SET category = 'TIANDI' "
            "WHERE category IS NULL OR category = ''"
        )
    )
    op.alter_column(
        "portal_accounts",
        "category",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("portal_accounts", "category")
