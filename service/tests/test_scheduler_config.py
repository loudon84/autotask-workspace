"""cron 解析、scheduler_config_service 与调度器热更单测（不连库）。"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.models.autotask_setting import AutotaskSetting
from app.services import scheduler_config_service as config_svc
from app.services.cron_schedule import CronParseError, CronSchedule, seconds_until_due
from app.services.scan_scheduler import ScanScheduler
from app.services.sign_poll_scheduler import SignPollScheduler


# ---------- CronSchedule ----------


def test_cron_parse_basic_forms():
    s = CronSchedule.parse("*/30 * * * *")
    assert s.minutes == frozenset({0, 30})
    s = CronSchedule.parse("0 8 * * *")
    assert s.minutes == {0} and s.hours == {8}
    s = CronSchedule.parse("0 8 * * 1-5")
    assert s.days_of_week == frozenset({1, 2, 3, 4, 5})
    s = CronSchedule.parse("10,40 8-18/2 * * 0,7")
    assert s.minutes == {10, 40}
    assert s.hours == {8, 10, 12, 14, 16, 18}
    assert s.days_of_week == {0}


def test_cron_parse_week_7_is_sunday():
    s = CronSchedule.parse("* * * * 7")
    assert 0 in s.days_of_week and 7 not in s.days_of_week


@pytest.mark.parametrize(
    "bad",
    [
        "* * * *",          # 4 段
        "60 * * * *",       # 分钟越界
        "* 24 * * *",       # 小时越界
        "a * * * *",        # 非数字
        "*/0 * * * *",      # 步长 0
        "5-1 * * * *",      # 范围倒置
        "30/15 * * * *",    # 单数字带步长（合法：30,45）
    ],
)
def test_cron_parse_invalid(bad):
    if bad == "30/15 * * * *":
        s = CronSchedule.parse(bad)  # 合法分支
        assert s.minutes == {30, 45}
        return
    with pytest.raises(CronParseError):
        CronSchedule.parse(bad)


def test_cron_next_after_every_30min():
    s = CronSchedule.parse("*/30 * * * *")
    t = datetime(2026, 8, 24, 9, 5)
    assert s.next_after(t) == datetime(2026, 8, 24, 9, 30)
    assert s.next_after(datetime(2026, 8, 24, 9, 30)) == datetime(2026, 8, 24, 10, 0)


def test_cron_next_after_daily_8am():
    s = CronSchedule.parse("0 8 * * *")
    t = datetime(2026, 8, 24, 8, 0, 30)  # 8 点整已过 30 秒
    assert s.next_after(t) == datetime(2026, 8, 25, 8, 0)


def test_cron_next_after_weekdays():
    s = CronSchedule.parse("0 8 * * 1-5")
    # 2026-08-24 是周一；周五 8:01 → 下周一
    assert s.next_after(datetime(2026, 8, 21, 8, 1)) == datetime(2026, 8, 24, 8, 0)
    # 周一 7:59 → 当天 8:00
    assert s.next_after(datetime(2026, 8, 24, 7, 59)) == datetime(2026, 8, 24, 8, 0)
    # 周六整点不触发 → 下周一
    assert s.next_after(datetime(2026, 8, 22, 7, 0)) == datetime(2026, 8, 24, 8, 0)


def test_cron_previous_before():
    s = CronSchedule.parse("0 8 * * *")
    assert s.previous_before(datetime(2026, 8, 24, 8, 5)) == datetime(2026, 8, 24, 8, 0)
    assert s.previous_before(datetime(2026, 8, 24, 7, 59)) == datetime(2026, 8, 23, 8, 0)


def test_cron_dom_dow_or_semantics():
    # 13 号 或 周五（Vixie OR）
    s = CronSchedule.parse("0 0 13 * 5")
    # 2026-08-13 周四（13 号命中）
    assert s.next_after(datetime(2026, 8, 12, 23, 0)) == datetime(2026, 8, 13, 0, 0)
    # 2026-08-14 周五（dow 命中）
    assert s.next_after(datetime(2026, 8, 13, 0, 1)) == datetime(2026, 8, 14, 0, 0)


def test_cron_impossible_date_raises():
    with pytest.raises(CronParseError):
        CronSchedule.parse("0 0 30 2 *").next_after(datetime(2026, 1, 1))


def test_seconds_until_due_wakes_at_cron_slot_not_next_30s_tick():
    # 现场：*/5 应对 15:10:00，但固定 30s tick 从 15:09:52 再睡 30s → 15:10:22
    due = datetime(2026, 8, 24, 15, 10, 0)
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 9, 52), 30.0) == 8.0
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 9, 38), 30.0) == 22.0
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 5, 0), 30.0) == 30.0
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 10, 0), 30.0) == 0.0


# ---------- scheduler_config_service ----------


def _settings(**overrides) -> Settings:
    defaults = {
        "SIGN_POLL_JOB_ENABLED": True,
        "SIGN_POLL_INTERVAL_SECONDS": 1800.0,
        "SCAN_JOB_ENABLED": True,
        "SCAN_JOB_HOUR": 8,
        "SCAN_JOB_MINUTE": 30,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self._rows)


class _Session:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.added: list[AutotaskSetting] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, _stmt):
        return _Result(self._rows)

    async def flush(self):
        return None

    def add(self, entity):
        self.added.append(entity)


def _row(key: str, value) -> tuple[str, str]:
    return (key, json.dumps(value))


@pytest.mark.asyncio
async def test_config_defaults_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_svc, "settings", _settings(SIGN_POLL_JOB_ENABLED=False))
    config = await config_svc.get_scheduler_config(_Session(rows=[]))
    assert config.sign_poll_enabled is False
    assert config.sign_poll_cron == "*/30 * * * *"
    assert config.scan_cron == "30 8 * * *"
    assert config.boe_pack_enabled is False
    assert config.boe_pack_cron == "0 7 * * *"


@pytest.mark.asyncio
async def test_config_reads_stored_cron(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_svc, "settings", _settings())
    session = _Session(
        rows=[
            _row(config_svc.KEY_SIGN_POLL_ENABLED, False),
            _row(config_svc.KEY_SIGN_POLL_CRON, "*/10 * * * *"),
            _row(config_svc.KEY_SCAN_ENABLED, True),
            _row(config_svc.KEY_SCAN_CRON, "0 8 * * 1-5"),
            _row(config_svc.KEY_BOE_PACK_ENABLED, True),
            _row(config_svc.KEY_BOE_PACK_CRON, "15 6 * * *"),
        ]
    )
    config = await config_svc.get_scheduler_config(session)
    assert config.sign_poll_enabled is False
    assert config.sign_poll_cron == "*/10 * * * *"
    assert config.scan_cron == "0 8 * * 1-5"
    assert config.boe_pack_enabled is True
    assert config.boe_pack_cron == "15 6 * * *"


@pytest.mark.asyncio
async def test_config_falls_back_on_invalid_stored_cron(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_svc, "settings", _settings())
    session = _Session(
        rows=[
            _row(config_svc.KEY_SIGN_POLL_CRON, "not a cron"),
            _row(config_svc.KEY_SCAN_CRON, 123),
        ]
    )
    config = await config_svc.get_scheduler_config(session)
    assert config.sign_poll_cron == "*/30 * * * *"
    assert config.scan_cron == "30 8 * * *"


@pytest.mark.asyncio
async def test_config_update_upserts_and_validates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_svc, "settings", _settings())
    existing_row = AutotaskSetting(
        tenant_id="t1", key=config_svc.KEY_SCAN_CRON, value='"0 8 * * *"'
    )
    session = _Session(rows=[existing_row])
    target = config_svc.SchedulerConfig(
        sign_poll_enabled=False,
        sign_poll_cron="*/15 * * * *",
        scan_enabled=True,
        scan_cron="0 9 * * 1-5",
        boe_pack_enabled=True,
        boe_pack_cron="0 7 * * *",
    )
    result = await config_svc.update_scheduler_config(session, target)
    assert result == target
    assert existing_row.value == '"0 9 * * 1-5"'
    added_keys = {item.key for item in session.added}
    assert added_keys == {
        config_svc.KEY_SIGN_POLL_ENABLED,
        config_svc.KEY_SIGN_POLL_CRON,
        config_svc.KEY_SCAN_ENABLED,
        config_svc.KEY_BOE_PACK_ENABLED,
        config_svc.KEY_BOE_PACK_CRON,
    }
    # 非法 cron 拒绝写入
    bad = config_svc.SchedulerConfig(
        sign_poll_enabled=True,
        sign_poll_cron="bad",
        scan_enabled=True,
        scan_cron="0 9 * * *",
        boe_pack_enabled=False,
        boe_pack_cron="0 7 * * *",
    )
    with pytest.raises(CronParseError):
        await config_svc.update_scheduler_config(_Session(), bad)


# ---------- 调度器热更与触发 ----------


def _config(sign_poll_enabled=True, sign_poll_cron="*/30 * * * *",
            scan_enabled=True, scan_cron="0 8 * * *",
            boe_pack_enabled=False, boe_pack_cron="0 7 * * *"):
    return config_svc.SchedulerConfig(
        sign_poll_enabled=sign_poll_enabled,
        sign_poll_cron=sign_poll_cron,
        scan_enabled=scan_enabled,
        scan_cron=scan_cron,
        boe_pack_enabled=boe_pack_enabled,
        boe_pack_cron=boe_pack_cron,
    )


@pytest.mark.asyncio
async def test_sign_poll_scheduler_skips_when_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        config_svc, "get_scheduler_config", AsyncMock(return_value=_config(sign_poll_enabled=False, scan_enabled=False))
    )
    forbidden = AsyncMock(side_effect=AssertionError("不应执行轮询"))
    scheduler = SignPollScheduler(_Session)
    monkeypatch.setattr(scheduler, "process_once", forbidden)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()
    forbidden.assert_not_awaited()


def test_sign_poll_apply_cron_waits_for_next_slot(monkeypatch: pytest.MonkeyPatch):
    # 现场：15:04:27 加载 */5 时把上个 15:00 当补跑，提前触发；应等到 15:05
    import app.services.sign_poll_scheduler as sign_mod

    frozen = datetime(2026, 8, 24, 15, 4, 27)

    class FrozenDateTime:
        @staticmethod
        def now():
            return frozen

    monkeypatch.setattr(sign_mod, "datetime", FrozenDateTime)
    scheduler = SignPollScheduler(_Session)
    scheduler._apply_cron("*/5 * * * *")
    assert scheduler._next_fire == datetime(2026, 8, 24, 15, 5, 0)


@pytest.mark.asyncio
async def test_sign_poll_scheduler_fires_when_due(monkeypatch: pytest.MonkeyPatch):
    import app.services.sign_poll_scheduler as sign_mod

    monkeypatch.setattr(sign_mod, "_TICK_SECONDS", 0.05)
    clock = {"t": datetime(2026, 8, 24, 15, 4, 50)}

    class FrozenDateTime:
        @staticmethod
        def now():
            return clock["t"]

    monkeypatch.setattr(sign_mod, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        config_svc,
        "get_scheduler_config",
        AsyncMock(return_value=_config(sign_poll_cron="*/5 * * * *", scan_enabled=False)),
    )
    process_once = AsyncMock(return_value=0)
    scheduler = SignPollScheduler(_Session)
    monkeypatch.setattr(scheduler, "process_once", process_once)

    await scheduler.start()
    await asyncio.sleep(0.15)
    process_once.assert_not_awaited()
    clock["t"] = datetime(2026, 8, 24, 15, 5, 0, 200_000)
    await asyncio.sleep(0.15)
    await scheduler.stop()
    process_once.assert_awaited()
    assert scheduler._next_fire == datetime(2026, 8, 24, 15, 10, 0)


@pytest.mark.asyncio
async def test_sign_poll_scheduler_far_future_cron_does_not_fire(monkeypatch: pytest.MonkeyPatch):
    # 2 月 29 日（仅闰年）且当前不在宽限窗口 → 不触发
    monkeypatch.setattr(
        config_svc,
        "get_scheduler_config",
        AsyncMock(return_value=_config(sign_poll_cron="0 0 29 2 *", scan_enabled=False)),
    )
    process_once = AsyncMock(return_value=0)
    scheduler = SignPollScheduler(_Session)
    monkeypatch.setattr(scheduler, "process_once", process_once)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()
    process_once.assert_not_awaited()


@pytest.mark.asyncio
async def test_scan_scheduler_hot_reloads_cron(monkeypatch: pytest.MonkeyPatch):
    import app.services.scan_scheduler as scan_mod
    monkeypatch.setattr(scan_mod, "_TICK_SECONDS", 0.05)
    current = {"cfg": _config(scan_cron="0 8 * * *", sign_poll_enabled=False)}
    monkeypatch.setattr(
        config_svc,
        "get_scheduler_config",
        AsyncMock(side_effect=lambda db, tenant_id=None: current["cfg"]),
    )
    process_once = AsyncMock(return_value=0)
    scheduler = ScanScheduler(_Session)
    monkeypatch.setattr(scheduler, "process_once", process_once)

    await scheduler.start()
    await asyncio.sleep(0.1)
    assert scheduler._cron_text == "0 8 * * *"
    # 热更表达式
    current["cfg"] = _config(scan_cron="*/15 * * * *", sign_poll_enabled=False)
    await asyncio.sleep(0.1)
    await scheduler.stop()
    assert scheduler._cron_text == "*/15 * * * *"


def test_scan_apply_cron_does_not_catch_up_previous_slot(monkeypatch: pytest.MonkeyPatch):
    import app.services.scan_scheduler as scan_mod

    frozen = datetime(2026, 8, 24, 15, 4, 27)

    class FrozenDateTime:
        @staticmethod
        def now():
            return frozen

    monkeypatch.setattr(scan_mod, "datetime", FrozenDateTime)
    scheduler = ScanScheduler(_Session)
    scheduler._apply_cron("*/5 * * * *")
    assert scheduler._next_fire == datetime(2026, 8, 24, 15, 5, 0)


@pytest.mark.asyncio
async def test_boe_pack_scheduler_skips_when_disabled(monkeypatch: pytest.MonkeyPatch):
    from app.services.boe_match_scheduler import BoeMatchScheduler

    monkeypatch.setattr(
        config_svc,
        "get_scheduler_config",
        AsyncMock(return_value=_config(boe_pack_enabled=False)),
    )
    forbidden = AsyncMock(side_effect=AssertionError("不应执行匹配"))
    scheduler = BoeMatchScheduler(_Session)
    monkeypatch.setattr(scheduler, "process_once", forbidden)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_boe_pack_scheduler_hot_reloads_cron(monkeypatch: pytest.MonkeyPatch):
    import app.services.boe_match_scheduler as boe_mod
    from app.services.boe_match_scheduler import BoeMatchScheduler

    monkeypatch.setattr(boe_mod, "_TICK_SECONDS", 0.05)
    current = {"cfg": _config(boe_pack_enabled=True, boe_pack_cron="0 7 * * *")}
    monkeypatch.setattr(
        config_svc,
        "get_scheduler_config",
        AsyncMock(side_effect=lambda db, tenant_id=None: current["cfg"]),
    )
    process_once = AsyncMock(return_value=0)
    scheduler = BoeMatchScheduler(_Session)
    monkeypatch.setattr(scheduler, "process_once", process_once)

    await scheduler.start()
    await asyncio.sleep(0.1)
    assert scheduler._cron_text == "0 7 * * *"
    current["cfg"] = _config(boe_pack_enabled=True, boe_pack_cron="15 6 * * *")
    await asyncio.sleep(0.1)
    await scheduler.stop()
    assert scheduler._cron_text == "15 6 * * *"
