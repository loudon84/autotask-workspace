"""定时器循环：到点 notify，不补跑（不连库）。"""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import timer_registry
from app.services import timer_service as timer_svc
from app.services.timer_scheduler import TimerScheduler


class _Session:
    captured: list = []

    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def add(self, entity):
        self.added.append(entity)
        _Session.captured.append(entity)

    async def flush(self):
        return None

    async def commit(self):
        return None


@pytest.fixture(autouse=True)
def _reset_registry():
    timer_registry.clear()
    _Session.captured = []
    yield
    timer_registry.clear()
    _Session.captured = []


@pytest.mark.asyncio
async def test_disabled_timers_are_not_listed_so_notify_skipped(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        timer_svc, "list_enabled_timers", AsyncMock(return_value=[])
    )
    spy = AsyncMock()
    timer_registry.register("t1", spy)
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    await asyncio.sleep(0.05)
    await scheduler.stop()
    spy.assert_not_awaited()


def test_apply_cron_does_not_catch_up_previous_slot(monkeypatch: pytest.MonkeyPatch):
    import app.services.timer_scheduler as sched_mod

    frozen = datetime(2026, 8, 24, 15, 4, 27)

    class FrozenDateTime:
        @staticmethod
        def now():
            return frozen

    monkeypatch.setattr(sched_mod, "datetime", FrozenDateTime)
    scheduler = TimerScheduler(_Session)
    job = SimpleNamespace(id="job-1", cron="*/5 * * * *", target="t1")
    scheduler._apply_job_cron(job, frozen)
    assert scheduler._next_fire["job-1"] == datetime(2026, 8, 24, 15, 5, 0)


@pytest.mark.asyncio
async def test_due_timer_notifies_registered_listener(monkeypatch: pytest.MonkeyPatch):
    import app.services.timer_scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "_TICK_SECONDS", 0.05)
    clock = {"t": datetime(2026, 8, 24, 15, 4, 50)}

    class FrozenDateTime:
        @staticmethod
        def now():
            return clock["t"]

    monkeypatch.setattr(sched_mod, "datetime", FrozenDateTime)
    job = SimpleNamespace(
        id="job-1", cron="*/5 * * * *", target="t1", enabled=True
    )
    monkeypatch.setattr(
        timer_svc, "list_enabled_timers", AsyncMock(return_value=[job])
    )
    spy = AsyncMock()
    timer_registry.register("t1", spy)
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    await asyncio.sleep(0.12)
    spy.assert_not_awaited()
    clock["t"] = datetime(2026, 8, 24, 15, 5, 0, 200_000)
    await asyncio.sleep(0.15)
    await scheduler.stop()
    spy.assert_awaited()
    assert scheduler._next_fire["job-1"] == datetime(2026, 8, 24, 15, 10, 0)
    success_runs = [r for r in _Session.captured if r.status == "SUCCESS"]
    assert success_runs, "到点应落一条 SUCCESS 执行记录"
    assert success_runs[0].finished_at is not None


@pytest.mark.asyncio
async def test_due_without_listener_does_not_fail(monkeypatch: pytest.MonkeyPatch):
    import app.services.timer_scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "_TICK_SECONDS", 0.05)
    clock = {"t": datetime(2026, 8, 24, 15, 4, 50)}

    class FrozenDateTime:
        @staticmethod
        def now():
            return clock["t"]

    monkeypatch.setattr(sched_mod, "datetime", FrozenDateTime)
    job = SimpleNamespace(
        id="job-1", cron="*/5 * * * *", target="missing", enabled=True
    )
    monkeypatch.setattr(
        timer_svc, "list_enabled_timers", AsyncMock(return_value=[job])
    )
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    await asyncio.sleep(0.12)
    clock["t"] = datetime(2026, 8, 24, 15, 5, 0, 200_000)
    await asyncio.sleep(0.15)
    await scheduler.stop()
    assert scheduler._next_fire["job-1"] == datetime(2026, 8, 24, 15, 10, 0)
    no_listener = [r for r in _Session.captured if r.status == "NO_LISTENER"]
    assert no_listener, "无入口也应落一条 NO_LISTENER 执行记录"


@pytest.mark.asyncio
async def test_listener_error_records_failed_run(monkeypatch: pytest.MonkeyPatch):
    import app.services.timer_scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "_TICK_SECONDS", 0.05)
    clock = {"t": datetime(2026, 8, 24, 15, 4, 50)}

    class FrozenDateTime:
        @staticmethod
        def now():
            return clock["t"]

    monkeypatch.setattr(sched_mod, "datetime", FrozenDateTime)
    job = SimpleNamespace(
        id="job-1", cron="*/5 * * * *", target="t1", enabled=True
    )
    monkeypatch.setattr(
        timer_svc, "list_enabled_timers", AsyncMock(return_value=[job])
    )

    async def boom():
        raise RuntimeError("入口炸了")

    timer_registry.register("t1", boom)
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    await asyncio.sleep(0.12)
    clock["t"] = datetime(2026, 8, 24, 15, 5, 0, 200_000)
    await asyncio.sleep(0.15)
    await scheduler.stop()
    failed = [r for r in _Session.captured if r.status == "FAILED"]
    assert failed, "入口抛错应落一条 FAILED 执行记录"
    assert "入口炸了" in (failed[0].error or "")
    assert scheduler._next_fire["job-1"] == datetime(2026, 8, 24, 15, 10, 0)
