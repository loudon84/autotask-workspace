"""流程实例排重：唯一索引只约束未作废、未软删的行。

Revision ID: f8c2e91b4a70
Revises: e7c2b9d04a18
Create Date: 2026-09-10 09:10:00

作废后定时器/立即匹配要能再 INSERT。全表唯一会 409。
2026-09-10 用户授权后已在测库执行（192.168.102.247 / nodeskclaw_task）。正式库未迁。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8c2e91b4a70"
down_revision: str | None = "e7c2b9d04a18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_process_instances_portal_code_biz",
        "process_instances",
        type_="unique",
    )
    op.create_index(
        "uq_process_instances_portal_code_biz_open",
        "process_instances",
        ["portal_account_id", "process_code", "biz_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status <> 'CANCELLED'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_process_instances_portal_code_biz_open",
        table_name="process_instances",
    )
    op.create_unique_constraint(
        "uq_process_instances_portal_code_biz",
        "process_instances",
        ["portal_account_id", "process_code", "biz_key"],
    )
