"""定时器执行记录表 timer_runs。未授权不得在演示/正式库执行。

Revision ID: d4b2f7a91e05
Revises: c3a8f1d92e47
Create Date: 2026-09-04 11:25:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4b2f7a91e05"
down_revision: str | None = "c3a8f1d92e47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timer_runs",
        sa.Column("timer_id", sa.String(length=36), nullable=False),
        sa.Column("target", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
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
        "ix_timer_runs_deleted_at",
        "timer_runs",
        ["deleted_at"],
        unique=False,
    )
    op.create_index("ix_timer_runs_timer_id", "timer_runs", ["timer_id"], unique=False)
    op.create_index(
        "ix_timer_runs_triggered_at", "timer_runs", ["triggered_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_timer_runs_triggered_at", table_name="timer_runs")
    op.drop_index("ix_timer_runs_timer_id", table_name="timer_runs")
    op.drop_index("ix_timer_runs_deleted_at", table_name="timer_runs")
    op.drop_table("timer_runs")
