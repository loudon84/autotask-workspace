"""增加后继任务作业和 Run 结构化输出。

Revision ID: 7c1f4d8e2a90
Revises: 00a7cf21c89d
Create Date: 2026-07-29 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "7c1f4d8e2a90"
down_revision: str | None = "00a7cf21c89d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rpa_runs",
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "automation_tasks",
        sa.Column("source_task_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "automation_tasks",
        sa.Column("source_run_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_automation_tasks_source_task_id",
        "automation_tasks",
        ["source_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_automation_tasks_source_run_id",
        "automation_tasks",
        ["source_run_id"],
        unique=False,
    )
    op.create_table(
        "task_successor_jobs",
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("source_task_id", sa.String(length=36), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column("target_workflow_binding_id", sa.String(length=36), nullable=False),
        sa.Column("input_mapper", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("successor_task_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_successor_jobs_deleted_at",
        "task_successor_jobs",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_successor_jobs_ready",
        "task_successor_jobs",
        ["status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_successor_jobs_tenant_source_task",
        "task_successor_jobs",
        ["tenant_id", "source_task_id"],
        unique=False,
    )
    op.create_index(
        "uq_task_successor_jobs_source_run_target",
        "task_successor_jobs",
        ["source_run_id", "target_workflow_binding_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_task_successor_jobs_source_run_target",
        table_name="task_successor_jobs",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_task_successor_jobs_tenant_source_task", table_name="task_successor_jobs")
    op.drop_index("ix_task_successor_jobs_ready", table_name="task_successor_jobs")
    op.drop_index("ix_task_successor_jobs_deleted_at", table_name="task_successor_jobs")
    op.drop_table("task_successor_jobs")
    op.drop_index("ix_automation_tasks_source_run_id", table_name="automation_tasks")
    op.drop_index("ix_automation_tasks_source_task_id", table_name="automation_tasks")
    op.drop_column("automation_tasks", "source_run_id")
    op.drop_column("automation_tasks", "source_task_id")
    op.drop_column("rpa_runs", "output")
