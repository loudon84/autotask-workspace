"""integration_call_logs：接口调用日志表（v5.4）。

一次主动 HTTP 一行，用 task_id 关联。记录 URL/入参/出参/状态/耗时，
写入前脱敏截断。运维从任务详情查看，不进证据中心。

Revision ID: b8c9d0e12f51
Revises: a7e4b2c81d09
Create Date: 2026-08-27 18:00:00

2026-08-27 用户授权后执行 alembic upgrade 至本 revision。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e12f51"
down_revision: str | None = "a7e4b2c81d09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_call_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("system", sa.String(length=32), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("request_body", sa.Text(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_truncated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("response_truncated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        "ix_integration_call_logs_task_created",
        "integration_call_logs",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_integration_call_logs_run_id",
        "integration_call_logs",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_integration_call_logs_deleted_at",
        "integration_call_logs",
        ["deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_integration_call_logs_deleted_at", table_name="integration_call_logs")
    op.drop_index("ix_integration_call_logs_run_id", table_name="integration_call_logs")
    op.drop_index("ix_integration_call_logs_task_created", table_name="integration_call_logs")
    op.drop_table("integration_call_logs")
