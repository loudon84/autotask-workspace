"""增加流程实例主任务与行级状态表。

Revision ID: 9a3f2c71b5d4
Revises: 7c1f4d8e2a90
Create Date: 2026-08-13 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9a3f2c71b5d4"
down_revision: str | None = "7c1f4d8e2a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "process_instances",
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("process_code", sa.String(length=128), nullable=False),
        sa.Column("biz_key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("portal_account_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("line_total", sa.Integer(), nullable=False),
        sa.Column("line_done", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portal_account_id",
            "process_code",
            "biz_key",
            name="uq_process_instances_portal_code_biz",
        ),
    )
    op.create_index(
        "ix_process_instances_deleted_at",
        "process_instances",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_process_instances_tenant_status",
        "process_instances",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_process_instances_tenant_stage",
        "process_instances",
        ["tenant_id", "stage"],
        unique=False,
    )
    op.create_table(
        "process_line_items",
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("line_number", sa.String(length=64), nullable=False),
        sa.Column("material_number", sa.String(length=255), nullable=False),
        sa.Column("item_name", sa.String(length=512), nullable=True),
        sa.Column("item_specification", sa.String(length=512), nullable=True),
        sa.Column("order_quantity", sa.String(length=64), nullable=True),
        sa.Column("order_quantity_uom", sa.String(length=32), nullable=True),
        sa.Column("request_date", sa.String(length=32), nullable=True),
        sa.Column("standard_delivery_days", sa.String(length=32), nullable=True),
        sa.Column("expected_delivery_date", sa.String(length=32), nullable=True),
        sa.Column("line_status", sa.String(length=32), nullable=False),
        sa.Column("sub_task_id", sa.String(length=36), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instance_id",
            "line_number",
            name="uq_process_line_items_instance_line",
        ),
    )
    op.create_index(
        "ix_process_line_items_deleted_at",
        "process_line_items",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_process_line_items_instance_status",
        "process_line_items",
        ["instance_id", "line_status"],
        unique=False,
    )
    op.create_table(
        "process_stage_history",
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("from_stage", sa.String(length=32), nullable=True),
        sa.Column("to_stage", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_process_stage_history_deleted_at",
        "process_stage_history",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_process_stage_history_instance",
        "process_stage_history",
        ["instance_id", "created_at"],
        unique=False,
    )
    op.add_column(
        "automation_tasks",
        sa.Column("process_instance_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_automation_tasks_process_instance_id",
        "automation_tasks",
        ["process_instance_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_automation_tasks_process_instance_id", table_name="automation_tasks")
    op.drop_column("automation_tasks", "process_instance_id")
    op.drop_index("ix_process_stage_history_instance", table_name="process_stage_history")
    op.drop_index("ix_process_stage_history_deleted_at", table_name="process_stage_history")
    op.drop_table("process_stage_history")
    op.drop_index("ix_process_line_items_instance_status", table_name="process_line_items")
    op.drop_index("ix_process_line_items_deleted_at", table_name="process_line_items")
    op.drop_table("process_line_items")
    op.drop_index("ix_process_instances_tenant_stage", table_name="process_instances")
    op.drop_index("ix_process_instances_tenant_status", table_name="process_instances")
    op.drop_index("ix_process_instances_deleted_at", table_name="process_instances")
    op.drop_table("process_instances")
