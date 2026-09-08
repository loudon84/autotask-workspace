"""门户增加分类专属 JSONB extra。通用列不变；BOE 邮箱等走 extra，不再加列。

Revision ID: e7c2b9d04a18
Revises: b2d4f6a81935
Create Date: 2026-09-08 15:50:00

说明：测试库已于 2026-09-08 经用户授权执行。正式库未授权，勿对正式 `.env` upgrade head。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7c2b9d04a18"
down_revision: str | None = "b2d4f6a81935"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_accounts",
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("portal_accounts", "extra")
