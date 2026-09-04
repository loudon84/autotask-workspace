"""独立定时器模型与 Alembic 文件约束（不连库、不执行 DDL）。"""

from pathlib import Path

from app.models.timer import Timer


def test_timer_columns_have_no_binding_or_portal():
    cols = {column.name for column in Timer.__table__.columns}
    assert "binding_id" not in cols
    assert "portal_account_id" not in cols
    assert {"id", "target", "name", "cron", "enabled"} <= cols


def test_alembic_timers_revision_creates_timers_not_binding():
    root = Path(__file__).resolve().parents[1]
    text = (root / "alembic" / "versions" / "c3a8f1d92e47_timers.py").read_text(
        encoding="utf-8"
    )
    assert 'create_table(\n        "timers"' in text
    assert "binding_id" not in text
    assert "portal_account_id" not in text
    assert 'down_revision: str | None = "a1c3e5f70824"' in text


def test_alembic_timer_runs_revision():
    root = Path(__file__).resolve().parents[1]
    text = (root / "alembic" / "versions" / "d4b2f7a91e05_timer_runs.py").read_text(
        encoding="utf-8"
    )
    assert 'create_table(\n        "timer_runs"' in text
    assert '"triggered_at"' in text
    assert '"finished_at"' in text
    assert 'down_revision: str | None = "c3a8f1d92e47"' in text
