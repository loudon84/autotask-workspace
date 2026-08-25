"""scheduler_jobs：一条 Binding 一行调度任务。

Revision ID: g3b8e2a91c40
Revises: f1a9c3e74b20
Create Date: 2026-08-24 17:20:00

dormant DDL：默认不在本会话执行；需用户明确授权后再 alembic upgrade。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g3b8e2a91c40"
down_revision: str | None = "f1a9c3e74b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduler_jobs",
        sa.Column("binding_id", sa.String(length=36), nullable=False),
        sa.Column("portal_account_id", sa.String(length=36), nullable=False),
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
        "ix_scheduler_jobs_deleted_at",
        "scheduler_jobs",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_scheduler_jobs_portal_account_id",
        "scheduler_jobs",
        ["portal_account_id"],
        unique=False,
    )
    op.create_index(
        "ix_scheduler_jobs_enabled",
        "scheduler_jobs",
        ["enabled"],
        unique=False,
    )
    op.create_index(
        "uq_scheduler_jobs_binding_id",
        "scheduler_jobs",
        ["binding_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_scheduler_jobs_binding_id",
        table_name="scheduler_jobs",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_scheduler_jobs_enabled", table_name="scheduler_jobs")
    op.drop_index("ix_scheduler_jobs_portal_account_id", table_name="scheduler_jobs")
    op.drop_index("ix_scheduler_jobs_deleted_at", table_name="scheduler_jobs")
    op.drop_table("scheduler_jobs")
