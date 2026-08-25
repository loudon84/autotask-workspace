"""标准 5 段 cron 表达式（分 时 日 月 周）解析与下次触发计算。

支持语法：`*`、`*/n`、`n`、`a-b`、`a-b/n`、`n/m`（等价 n-hi/m）、逗号列表（可混搭）。
日(dom) 与 周(dow) 同时受限时按 Vixie cron 语义取 OR（任一匹配即触发）；
其中一方为 `*` 时另一方单独决定。周 0 与 7 均表示周日。

`*/30 * * * *` = 每半小时；`0 8 * * *` = 每天 8 点；`0 8 * * 1-5` = 工作日 8 点。
仅用于本地时间触发推算，不引入第三方依赖。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

_FIELDS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day_of_month", 1, 31),
    ("month", 1, 12),
    ("day_of_week", 0, 7),
)

# next_after 逐字段跳进的安全迭代上限（覆盖数年也无解的病态表达式）
_MAX_SEARCH_STEPS = 200_000

# day_of_week 解析时 7 归一化为 0，因此"全周"集合为 {0..6}
_ANY_DOW = frozenset(range(0, 7))


class CronParseError(ValueError):
    """cron 表达式非法或无有效触发时刻。"""


@dataclass(frozen=True)
class CronSchedule:
    minutes: frozenset[int]
    hours: frozenset[int]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]

    @classmethod
    def parse(cls, expression: str) -> "CronSchedule":
        parts = expression.strip().split()
        if len(parts) != 5:
            raise CronParseError("cron 需为 5 段：分 时 日 月 周")
        sets: list[frozenset[int]] = []
        for (name, lo, hi), raw in zip(_FIELDS, parts):
            allowed = _parse_field(name, lo, hi, raw)
            if not allowed:
                raise CronParseError(f"cron {name} 字段为空: {raw!r}")
            sets.append(frozenset(allowed))
        return cls(*sets)

    def next_after(self, dt: datetime) -> datetime:
        """返回严格晚于 dt 的下一个触发时刻（分钟粒度，本地时间）。"""
        t = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(_MAX_SEARCH_STEPS):
            if t.month not in self.months:
                t = _jump_to_next_month(t)
                continue
            if not self._day_matches(t):
                t = _jump_to_next_day(t)
                continue
            if t.hour not in self.hours:
                t = _jump_to_next_hour(t)
                continue
            if t.minute not in self.minutes:
                t = _jump_to_next_minute(t)
                continue
            return t
        raise CronParseError("cron 表达式在可搜索范围内无有效触发时刻（如 2 月 30 日）")

    def previous_before(self, dt: datetime) -> datetime:
        """返回严格早于 dt 的上一个触发时刻（分钟粒度，本地时间）。"""
        t = dt.replace(second=0, microsecond=0) - timedelta(minutes=1)
        for _ in range(_MAX_SEARCH_STEPS):
            if t.month not in self.months:
                t = _jump_to_prev_month_end(t)
                continue
            if not self._day_matches(t):
                t = _jump_to_prev_day(t)
                continue
            if t.hour not in self.hours:
                t = _jump_to_prev_hour(t)
                continue
            if t.minute not in self.minutes:
                t = _jump_to_prev_minute(t)
                continue
            return t
        raise CronParseError("cron 表达式在可搜索范围内无有效触发时刻（如 2 月 30 日）")

    def _day_matches(self, t: datetime) -> bool:
        dom_any = self.days_of_month == frozenset(range(1, 32))
        dow_any = self.days_of_week == _ANY_DOW
        dom_hit = t.day in self.days_of_month
        # Python weekday(): 周一=0 … 周日=6；cron 周日=0/7
        cron_dow = (t.weekday() + 1) % 7
        dow_hit = cron_dow in self.days_of_week
        # Vixie 语义：双方都受限取 OR；仅一方受限由该方决定；都为 * 恒真
        if dom_any and dow_any:
            return True
        if dom_any:
            return dow_hit
        if dow_any:
            return dom_hit
        return dom_hit or dow_hit


def _parse_field(name: str, lo: int, hi: int, raw: str) -> set[int]:
    allowed: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            raise CronParseError(f"cron {name} 字段含空段: {raw!r}")
        step = 1
        if "/" in chunk:
            base, step_text = chunk.split("/", 1)
            try:
                step = int(step_text)
            except ValueError:
                raise CronParseError(f"cron {name} 步长非法: {chunk!r}") from None
            if step <= 0:
                raise CronParseError(f"cron {name} 步长需为正整数: {chunk!r}")
        else:
            base = chunk
        single_number = False
        if base == "*":
            start, end = lo, hi
        elif "-" in base and not base.startswith("-"):
            a, b = base.split("-", 1)
            try:
                start, end = int(a), int(b)
            except ValueError:
                raise CronParseError(f"cron {name} 范围非法: {chunk!r}") from None
        else:
            try:
                start = end = int(base)
            except ValueError:
                raise CronParseError(f"cron {name} 取值非法: {chunk!r}") from None
            single_number = True
        if start < lo or end > hi or start > end:
            raise CronParseError(f"cron {name} 取值越界（{lo}-{hi}）: {chunk!r}")
        # 单数字带步长（如 分钟 30/15 → 30,45）扩展到字段上限
        if single_number and step != 1:
            end = hi
        allowed.update(range(start, end + 1, step))
    if name == "day_of_week" and 7 in allowed:
        allowed.discard(7)
        allowed.add(0)
    return allowed


def _jump_to_next_month(t: datetime) -> datetime:
    if t.month == 12:
        return t.replace(year=t.year + 1, month=1, day=1, hour=0, minute=0)
    return t.replace(month=t.month + 1, day=1, hour=0, minute=0)


def _jump_to_prev_month_end(t: datetime) -> datetime:
    first_of_month = t.replace(day=1, hour=0, minute=0)
    return first_of_month - timedelta(minutes=1)


def _jump_to_prev_day(t: datetime) -> datetime:
    return t.replace(hour=0, minute=0) - timedelta(minutes=1)


def _jump_to_prev_hour(t: datetime) -> datetime:
    return t.replace(minute=0) - timedelta(minutes=1)


def _jump_to_prev_minute(t: datetime) -> datetime:
    return t - timedelta(minutes=1)


def _jump_to_next_day(t: datetime) -> datetime:
    return t.replace(hour=0, minute=0) + timedelta(days=1)


def _jump_to_next_hour(t: datetime) -> datetime:
    return t.replace(minute=0) + timedelta(hours=1)


def _jump_to_next_minute(t: datetime) -> datetime:
    return t + timedelta(minutes=1)


def seconds_until_due(
    next_fire: datetime | None,
    now: datetime,
    max_wait: float,
) -> float:
    """距下次触发还要睡多久。

    到点附近按剩余秒数醒，避免固定 30s tick 把触发拖到 15:10:22；
    平时最多睡 max_wait，以便开关/cron 热加载。
    """
    if next_fire is None:
        return max_wait
    remaining = (next_fire - now).total_seconds()
    if remaining <= 0:
        return 0.0
    return min(max_wait, remaining)
