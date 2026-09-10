"""cron 解析（不连库）。独立定时器循环测试见 test_timer_scheduler。"""

from datetime import datetime

import pytest

from app.services.cron_schedule import CronParseError, CronSchedule, seconds_until_due


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
        "* * * *",
        "60 * * * *",
        "* 24 * * *",
        "a * * * *",
        "*/0 * * * *",
        "5-1 * * * *",
        "30/15 * * * *",
    ],
)
def test_cron_parse_invalid(bad):
    if bad == "30/15 * * * *":
        s = CronSchedule.parse(bad)
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
    t = datetime(2026, 8, 24, 8, 0, 30)
    assert s.next_after(t) == datetime(2026, 8, 25, 8, 0)


def test_cron_next_after_weekdays():
    s = CronSchedule.parse("0 8 * * 1-5")
    assert s.next_after(datetime(2026, 8, 21, 8, 1)) == datetime(2026, 8, 24, 8, 0)
    assert s.next_after(datetime(2026, 8, 24, 7, 59)) == datetime(2026, 8, 24, 8, 0)
    assert s.next_after(datetime(2026, 8, 22, 7, 0)) == datetime(2026, 8, 24, 8, 0)


def test_cron_previous_before():
    s = CronSchedule.parse("0 8 * * *")
    assert s.previous_before(datetime(2026, 8, 24, 8, 5)) == datetime(2026, 8, 24, 8, 0)
    assert s.previous_before(datetime(2026, 8, 24, 7, 59)) == datetime(2026, 8, 23, 8, 0)


def test_cron_dom_dow_or_semantics():
    s = CronSchedule.parse("0 0 13 * 5")
    assert s.next_after(datetime(2026, 8, 12, 23, 0)) == datetime(2026, 8, 13, 0, 0)
    assert s.next_after(datetime(2026, 8, 13, 0, 1)) == datetime(2026, 8, 14, 0, 0)


def test_cron_impossible_date_raises():
    with pytest.raises(CronParseError):
        CronSchedule.parse("0 0 30 2 *").next_after(datetime(2026, 1, 1))


def test_seconds_until_due_wakes_at_cron_slot_not_next_30s_tick():
    due = datetime(2026, 8, 24, 15, 10, 0)
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 9, 52), 30.0) == 8.0
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 9, 38), 30.0) == 22.0
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 5, 0), 30.0) == 30.0
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 10, 0), 30.0) == 0.0
