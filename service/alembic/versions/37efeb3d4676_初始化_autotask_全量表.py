"""初始化 AutoTask 全量表

Revision ID: 37efeb3d4676
Revises:
Create Date: 2026-07-07 14:18:12.913204

"""

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "37efeb3d4676"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
