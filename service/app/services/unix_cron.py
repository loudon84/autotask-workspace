"""crontab 5 段表达式 → APScheduler CronTrigger 的转换垫片。

APScheduler 3 的 day_of_week：0=周一、只认 0-6、7 报错、名字顺序 mon…sun；
crontab：0/7=周日、1-5=周一到周五。两边语义不同，不能直接把库里的 crontab
表达式交给 from_crontab，必须先过 to_apscheduler_crontab 转换第 5 段。

开火（timer_scheduler）与 next_run_at/保存校验（timer_service）必须共用
build_cron_trigger，禁止一处垫片一处直接 from_crontab。
"""

from __future__ import annotations

from apscheduler.triggers.cron import CronTrigger

from app.services.china_clock import CHINA_TZ

# 索引 = crontab dow 数字（0/7=周日）
_DOW_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
_DOW_MAX = 7


class UnixCronError(ValueError):
    """crontab 表达式非法（段数不对或 dow 段写法越界）。"""


def to_apscheduler_crontab(expr: str) -> str:
    """crontab 5 段 → APScheduler 兼容表达式。只转换第 5 段（dow），其余原样。"""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise UnixCronError("cron 需为 5 段：分 时 日 月 周")
    parts[4] = _convert_dow(parts[4])
    return " ".join(parts)


def build_cron_trigger(cron: str) -> CronTrigger:
    """crontab 5 段 → CronTrigger（上海时区）。非法表达式抛 ValueError。"""
    return CronTrigger.from_crontab(to_apscheduler_crontab(cron), timezone=CHINA_TZ)


def _convert_dow(field: str) -> str:
    """dow 段数字转英文名。范围展开成名字列表，不输出 sun-sat 这类跨周范围
    （APScheduler 名字顺序是 mon…sun，跨周范围会错）。"""
    if field == "*":
        return field
    names: list[str] = []
    for chunk in field.split(","):
        chunk = chunk.strip()
        if not chunk:
            raise UnixCronError(f"cron day_of_week 字段含空段: {field!r}")
        if any(c.isalpha() for c in chunk):
            names.append(chunk)
            continue
        base, sep, step_text = chunk.partition("/")
        step = 1
        if sep:
            try:
                step = int(step_text)
            except ValueError:
                raise UnixCronError(f"cron day_of_week 步长非法: {chunk!r}") from None
            if step <= 0:
                raise UnixCronError(f"cron day_of_week 步长需为正整数: {chunk!r}")
        if base == "*":
            start, end = 0, 6  # crontab dow 的 * 覆盖 0-6（7 与 0 同为周日）
        elif "-" in base:
            a, b = base.split("-", 1)
            try:
                start, end = int(a), int(b)
            except ValueError:
                raise UnixCronError(f"cron day_of_week 范围非法: {chunk!r}") from None
        else:
            try:
                start = int(base)
            except ValueError:
                raise UnixCronError(f"cron day_of_week 取值非法: {chunk!r}") from None
            # 单数字带步长（如 5/2）扩展到字段上限，与旧 CronSchedule 语义一致
            end = _DOW_MAX if step != 1 else start
        if start < 0 or end > _DOW_MAX or start > end:
            raise UnixCronError(f"cron day_of_week 取值越界（0-7）: {chunk!r}")
        for value in range(start, end + 1, step):
            name = _DOW_NAMES[value % 7]
            if name not in names:
                names.append(name)
    return ",".join(names)
