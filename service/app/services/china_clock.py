"""调度中心 cron 用中国墙上时钟，不跟 4520 机器时区、不跟数据库 UTC。"""

from datetime import datetime
from zoneinfo import ZoneInfo

CHINA_TZ = ZoneInfo("Asia/Shanghai")


def now_china() -> datetime:
    """naive 中国本地时间，给 5 段 cron 用。"""
    return datetime.now(CHINA_TZ).replace(tzinfo=None)
