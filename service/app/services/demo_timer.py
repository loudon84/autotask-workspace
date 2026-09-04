"""演示定时器：到点打印当前时间。登记入口，不依赖门户或 Binding。"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DEMO_PRINT_NOW_TARGET = "demo.print_now"


async def print_current_time() -> None:
    """到点只打一行当前时间；不读库、不碰业务。"""
    logger.info("演示定时器到点：%s", datetime.now().isoformat(timespec="seconds"))
