"""独立定时器表 timers。未授权不得在演示/正式库执行。

Revision ID: c3a8f1d92e47
Revises: a1c3e5f70824
Create Date: 2026-09-04 09:54:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3a8f1d92e47"
down_revision: str | None = "a1c3e5f70824"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timers",
        sa.Column("target", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("cron", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_timers_deleted_at",
        "timers",
        ["deleted_at"],
        unique=False,
    )
    op.create_index("ix_timers_enabled", "timers", ["enabled"], unique=False)
    op.create_index(
        "uq_timers_target",
        "timers",
        ["target"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_timers_target",
        table_name="timers",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_timers_enabled", table_name="timers")
    op.drop_index("ix_timers_deleted_at", table_name="timers")
    op.drop_table("timers")
