"""定时器执行记录服务：开始/结束/状态流转（不连库）。"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.timer_run import (
    TIMER_RUN_FAILED,
    TIMER_RUN_NO_LISTENER,
    TIMER_RUN_RUNNING,
    TIMER_RUN_SUCCESS,
)
from app.services import timer_run_service as run_svc


def _db():
    db = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_record_start_is_running_with_triggered_at():
    db = _db()
    at = datetime(2026, 9, 4, 8, 0, 0)
    run = await run_svc.record_start(
        db, timer_id="t1", target="demo.print_now", triggered_at=at
    )
    assert run.status == TIMER_RUN_RUNNING
    assert run.triggered_at == at
    assert run.finished_at is None
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_record_finish_success():
    db = _db()
    run = await run_svc.record_start(
        db, timer_id="t1", target="t", triggered_at=datetime.now()
    )
    await run_svc.record_finish(db, run, ok=True)
    assert run.status == TIMER_RUN_SUCCESS
    assert run.finished_at is not None
    assert run.error is None


@pytest.mark.asyncio
async def test_record_finish_failed_keeps_error():
    db = _db()
    run = await run_svc.record_start(
        db, timer_id="t1", target="t", triggered_at=datetime.now()
    )
    await run_svc.record_finish(db, run, ok=False, error="boom")
    assert run.status == TIMER_RUN_FAILED
    assert run.error == "boom"


@pytest.mark.asyncio
async def test_record_finish_no_listener():
    db = _db()
    run = await run_svc.record_start(
        db, timer_id="t1", target="t", triggered_at=datetime.now()
    )
    await run_svc.record_finish(db, run, ok=True, had_listener=False)
    assert run.status == TIMER_RUN_NO_LISTENER


def _timer(*, enabled: bool = False):
    timer = MagicMock()
    timer.id = "t1"
    timer.target = "test.run_now"
    timer.enabled = enabled
    return timer


@pytest.mark.asyncio
async def test_run_timer_now_ignores_enabled_and_records_success():
    """立即执行不看开关：停用的定时器也照常触发并落记录。"""
    from app.services import timer_registry

    calls: list[str] = []

    async def entry() -> None:
        calls.append("fired")

    timer_registry.register("test.run_now", entry)
    try:
        db = _db()
        run = await run_svc.run_timer_now(db, _timer(enabled=False))
        assert calls == ["fired"]
        assert run.status == TIMER_RUN_SUCCESS
        assert run.finished_at is not None
    finally:
        timer_registry.clear()


@pytest.mark.asyncio
async def test_run_timer_now_entry_error_records_failed():
    from app.services import timer_registry

    async def entry() -> None:
        raise RuntimeError("boom")

    timer_registry.register("test.run_now", entry)
    try:
        db = _db()
        run = await run_svc.run_timer_now(db, _timer())
        assert run.status == TIMER_RUN_FAILED
        assert run.error == "boom"
    finally:
        timer_registry.clear()


@pytest.mark.asyncio
async def test_run_timer_now_no_listener_records_no_listener():
    from app.services import timer_registry

    timer_registry.clear()
    db = _db()
    run = await run_svc.run_timer_now(db, _timer())
    assert run.status == TIMER_RUN_NO_LISTENER
