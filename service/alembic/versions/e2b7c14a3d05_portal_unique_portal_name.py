"""门户唯一性从 (地址+登录账号) 改为门户名称。

Revision ID: e2b7c14a3d05
Revises: d8f3a1b62c90
Create Date: 2026-08-19 17:00:00

说明：本迁移为 dormant DDL，默认不在本会话执行；需用户明确授权后再 alembic upgrade。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e2b7c14a3d05"
down_revision: str | None = "d8f3a1b62c90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_portal_accounts_tenant_entity_url_login",
        table_name="portal_accounts",
        if_exists=True,
    )
    op.create_index(
        "uq_portal_accounts_tenant_portal_name",
        "portal_accounts",
        ["tenant_id", "portal_name"],
        unique=True,
        postgresql_where=op.f("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_portal_accounts_tenant_portal_name",
        table_name="portal_accounts",
    )
    op.create_index(
        "uq_portal_accounts_tenant_entity_url_login",
        "portal_accounts",
        ["tenant_id", "entity_type", "portal_url", "login_account"],
        unique=True,
        postgresql_where=op.f("deleted_at IS NULL"),
    )
