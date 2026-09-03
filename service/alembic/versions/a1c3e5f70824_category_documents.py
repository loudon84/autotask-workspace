"""门户分类文档表：按硬编码 category code 存操作手册等文件。

Revision ID: a1c3e5f70824
Revises: d2e9f1a70b83
Create Date: 2026-09-03 12:20:00

分类码仍写死在代码；本表只存 TIANDI/BOE 字符串。文件在 Task 磁盘
ARTIFACT_LOCAL_DIR/category-docs/。未授权不得在演示/正式库执行。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c3e5f70824"
down_revision: str | None = "d2e9f1a70b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "category_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", sa.String(length=36), nullable=False),
        sa.Column("uploaded_by_name", sa.String(length=255), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_category_documents_tenant_category",
        "category_documents",
        ["tenant_id", "category"],
    )
    op.create_index("ix_category_documents_deleted_at", "category_documents", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_category_documents_deleted_at", table_name="category_documents")
    op.drop_index("ix_category_documents_tenant_category", table_name="category_documents")
    op.drop_table("category_documents")
