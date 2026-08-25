"""user_cache 增加 is_task_admin（AutoTask 模块管理员）。

Revision ID: a7e4b2c81d09
Revises: g3b8e2a91c40
Create Date: 2026-08-25 10:30:00

dormant DDL：未授权不执行 alembic upgrade。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7e4b2c81d09"
down_revision: str | None = "g3b8e2a91c40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "autotask_user_cache",
        sa.Column(
            "is_task_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("autotask_user_cache", "is_task_admin")
