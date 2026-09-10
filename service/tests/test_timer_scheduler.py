"""定时器调度：APScheduler 同步 + 到点 notify（不连库）。"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.services import timer_registry
from app.services import timer_service as timer_svc
from app.services.timer_scheduler import TimerScheduler
from app.services.unix_cron import build_cron_trigger, to_apscheduler_crontab

SHANGHAI = ZoneInfo("Asia/Shanghai")


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


def _timer(timer_id: str, cron: str, target: str = "t1"):
    return SimpleNamespace(id=timer_id, cron=cron, target=target, enabled=True)


# ---- 同步：库里启用行 ↔ 框架 job ----


@pytest.mark.asyncio
async def test_enabled_timer_is_added_with_timer_id_as_job_id(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        timer_svc,
        "list_enabled_timers",
        AsyncMock(return_value=[_timer("job-1", "0 8 * * *")]),
    )
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    try:
        await scheduler._sync_once()
        job = scheduler._scheduler.get_job("job-1")
        assert job is not None, "启用行应同步成框架 job，且 job id == timer.id"
        assert list(job.args) == ["job-1", "t1"]
        assert job.misfire_grace_time == 120
        assert job.max_instances == 1
        assert job.coalesce is True
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_disabled_or_removed_timer_job_is_removed(
    monkeypatch: pytest.MonkeyPatch,
):
    rows = [_timer("job-1", "0 8 * * *")]
    monkeypatch.setattr(
        timer_svc, "list_enabled_timers", AsyncMock(side_effect=lambda db: rows.copy())
    )
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    try:
        await scheduler._sync_once()
        assert scheduler._scheduler.get_job("job-1") is not None
        rows.clear()  # 停用/删除后下一轮同步应摘掉
        await scheduler._sync_once()
        assert scheduler._scheduler.get_job("job-1") is None
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_invalid_cron_is_not_scheduled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        timer_svc,
        "list_enabled_timers",
        AsyncMock(return_value=[_timer("bad-1", "not a cron")]),
    )
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    try:
        await scheduler._sync_once()
        assert scheduler._scheduler.get_job("bad-1") is None
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_unchanged_cron_does_not_replace_job(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        timer_svc,
        "list_enabled_timers",
        AsyncMock(return_value=[_timer("job-1", "0 8 * * *")]),
    )
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    try:
        await scheduler._sync_once()
        job = scheduler._scheduler.get_job("job-1")
        first_next = job.next_run_time
        orig = scheduler._scheduler.add_job
        calls = {"n": 0}

        def counting(*args, **kwargs):
            calls["n"] += 1
            return orig(*args, **kwargs)

        scheduler._scheduler.add_job = counting  # type: ignore[method-assign]
        await scheduler._sync_once()
        assert calls["n"] == 0, "同一 cron 不得 replace_existing，否则 misfire 宽限被冲掉"
        assert scheduler._scheduler.get_job("job-1").next_run_time == first_next
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_cron_change_reschedules_same_job_id(
    monkeypatch: pytest.MonkeyPatch,
):
    rows = [_timer("job-1", "0 8 * * *")]
    monkeypatch.setattr(
        timer_svc, "list_enabled_timers", AsyncMock(side_effect=lambda db: rows.copy())
    )
    scheduler = TimerScheduler(_Session)
    await scheduler.start()
    try:
        await scheduler._sync_once()
        rows[0] = _timer("job-1", "0 9 * * *")
        await scheduler._sync_once()
        job = scheduler._scheduler.get_job("job-1")
        assert job is not None
        nxt = job.trigger.get_next_fire_time(
            None, datetime(2026, 8, 24, 0, 0, tzinfo=SHANGHAI)
        )
        assert nxt is not None
        assert nxt.astimezone(SHANGHAI).hour == 9
    finally:
        await scheduler.stop()


# ---- 时区与不补跑（以真实 Trigger 为准）----


def test_cron_uses_shanghai_wall_clock_not_host():
    # 任意「现在」，下次触发的小时必须是上海墙上的 9 点
    now = datetime(2026, 8, 24, 3, 0, tzinfo=SHANGHAI)
    nxt = build_cron_trigger("5 9 * * *").get_next_fire_time(None, now)
    assert nxt is not None
    shanghai_next = nxt.astimezone(SHANGHAI)
    assert (shanghai_next.hour, shanghai_next.minute) == (9, 5)
    assert shanghai_next.utcoffset().total_seconds() == 8 * 3600


def test_next_fire_is_strictly_after_now_no_catch_up():
    now = datetime(2026, 8, 24, 15, 4, 27, tzinfo=SHANGHAI)
    nxt = build_cron_trigger("*/5 * * * *").get_next_fire_time(None, now)
    assert nxt == datetime(2026, 8, 24, 15, 5, tzinfo=SHANGHAI)


# ---- dow 垫片：crontab 0/7=周日，APScheduler 0=周一 ----


def test_dow_weekday_range_fires_monday_to_friday():
    # 2026-08-24 是周一；从周六凌晨探，下次应是周一 08:00 而不是周日/周二
    now = datetime(2026, 8, 22, 3, 0, tzinfo=SHANGHAI)  # 周六
    nxt = build_cron_trigger("0 8 * * 1-5").get_next_fire_time(None, now)
    assert nxt == datetime(2026, 8, 24, 8, 0, tzinfo=SHANGHAI)
    assert nxt.weekday() == 0


def test_dow_zero_and_seven_both_mean_sunday():
    now = datetime(2026, 8, 24, 3, 0, tzinfo=SHANGHAI)  # 周一
    for expr in ("* * * * 0", "* * * * 7"):
        nxt = build_cron_trigger(expr).get_next_fire_time(None, now)
        assert nxt is not None
        assert nxt.weekday() == 6, f"{expr} 下次触发应是周日"
        assert (nxt.date() - now.date()).days <= 7


def test_dow_shim_text_conversion():
    assert to_apscheduler_crontab("0 8 * * 1-5") == "0 8 * * mon,tue,wed,thu,fri"
    assert to_apscheduler_crontab("* * * * 0,6") == "* * * * sun,sat"
    assert to_apscheduler_crontab("* * * * *") == "* * * * *"
    assert to_apscheduler_crontab("10,40 8-18/2 * * 0,7") == "10,40 8-18/2 * * sun"


# ---- _fire：直接调，覆盖 SUCCESS / NO_LISTENER / FAILED ----


@pytest.mark.asyncio
async def test_fire_success_records_run():
    spy = AsyncMock(return_value="摘要")
    timer_registry.register("t1", spy)
    scheduler = TimerScheduler(_Session)
    await scheduler._fire("job-1", "t1")
    spy.assert_awaited_once()
    success = [r for r in _Session.captured if r.status == "SUCCESS"]
    assert success, "到点应落一条 SUCCESS 执行记录"
    assert success[0].finished_at is not None
    assert success[0].error == "摘要"


@pytest.mark.asyncio
async def test_fire_without_listener_records_no_listener():
    scheduler = TimerScheduler(_Session)
    await scheduler._fire("job-1", "missing")
    no_listener = [r for r in _Session.captured if r.status == "NO_LISTENER"]
    assert no_listener, "无入口应落一条 NO_LISTENER 执行记录"


@pytest.mark.asyncio
async def test_fire_listener_error_records_failed():
    async def boom():
        raise RuntimeError("入口炸了")

    timer_registry.register("t1", boom)
    scheduler = TimerScheduler(_Session)
    await scheduler._fire("job-1", "t1")
    failed = [r for r in _Session.captured if r.status == "FAILED"]
    assert failed, "入口抛错应落一条 FAILED 执行记录"
    assert "入口炸了" in (failed[0].error or "")


def test_now_china_is_shanghai_wall_clock():
    from app.services.china_clock import now_china

    china = datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    got = now_china()
    assert abs((got - china).total_seconds()) < 2
