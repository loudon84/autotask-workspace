"""定时器管理服务：改 cron、登记插入不覆盖（不连库）。"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import UnprocessableError
from app.models.timer import Timer
from app.schemas.timer import TimerResponse
from app.services import timer_service as timer_svc
from app.services.timer_catalog import TimerRegistration


@pytest.mark.asyncio
async def test_update_timer_rejects_invalid_cron():
    timer = Timer(id="1", target="t1", name="n", cron="0 8 * * *", enabled=False)
    db = MagicMock()
    db.flush = AsyncMock()
    with pytest.raises(UnprocessableError):
        await timer_svc.update_timer(db, timer, cron="not a cron")
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_timer_accepts_valid_cron():
    timer = Timer(id="1", target="t1", name="n", cron="0 8 * * *", enabled=True)
    db = MagicMock()
    db.flush = AsyncMock()
    result = await timer_svc.update_timer(
        db, timer, name="改名", enabled=True, cron="0 9 * * *"
    )
    assert result.cron == "0 9 * * *"
    assert result.name == "改名"
    db.flush.assert_awaited()


def test_timer_response_has_no_portal_binding_or_target():
    timer = Timer(
        id="1",
        target="secret.target",
        name="演示",
        cron="0 8 * * *",
        enabled=False,
    )
    payload = TimerResponse(
        id=timer.id,
        name=timer.name,
        cron=timer.cron,
        enabled=timer.enabled,
        next_run_at=None,
    ).model_dump(by_alias=True)
    assert "target" not in payload
    assert "portalName" not in payload
    assert "bindingId" not in payload
    assert set(payload) == {"id", "name", "cron", "enabled", "nextRunAt"}


@pytest.mark.asyncio
async def test_ensure_catalog_inserts_once_and_does_not_override(
    monkeypatch: pytest.MonkeyPatch,
):
    store: dict[str, Timer] = {}

    async def fake_get(_db, target: str):
        return store.get(target)

    monkeypatch.setattr(timer_svc, "get_timer_by_target", fake_get)

    class _Db:
        def add(self, entity: Timer) -> None:
            store[entity.target] = entity

        async def flush(self) -> None:
            return None

    db = _Db()
    regs = [
        TimerRegistration(
            target="demo.print_now",
            name="打印当前时间",
            cron="* * * * *",
            enabled=False,
        )
    ]
    created = await timer_svc.ensure_catalog_rows(db, regs)
    assert created == 1
    store["demo.print_now"].enabled = True
    store["demo.print_now"].cron = "0 7 * * *"
    created_again = await timer_svc.ensure_catalog_rows(
        db,
        [
            TimerRegistration(
                target="demo.print_now",
                name="会被忽略",
                cron="0 8 * * *",
                enabled=False,
            )
        ],
    )
    assert created_again == 0
    assert store["demo.print_now"].enabled is True
    assert store["demo.print_now"].cron == "0 7 * * *"
    assert store["demo.print_now"].name == "打印当前时间"


def test_next_run_at_null_when_disabled():
    assert timer_svc.next_run_at("0 8 * * *", False) is None
    nxt = timer_svc.next_run_at("0 8 * * *", True, datetime(2026, 8, 24, 7, 0))
    assert nxt == datetime(2026, 8, 24, 8, 0)


def test_production_catalog_entries():
    from app.services.timer_catalog import REGISTRATIONS

    by_target = {item.target: item for item in REGISTRATIONS}
    assert set(by_target) == {
        "demo.print_now",
        "tiandy.scan_pending",
        "tiandy.sign_poll",
    }
    assert by_target["demo.print_now"].cron == "0 8 * * *"
    assert by_target["tiandy.scan_pending"].cron == "0 8 * * *"
    assert by_target["tiandy.sign_poll"].cron == "*/30 * * * *"
    assert all(item.enabled is False for item in REGISTRATIONS)
