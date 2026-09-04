"""天地伟业定时器入口：到点做什么写在这里，调度内核只负责 notify。

- tiandy.scan_pending：为所有启用扫单 Binding 的天地伟业门户建扫单任务
- tiandy.sign_poll：跑一轮回签探测

开关与 cron 在调度中心维护（timers 表），本模块不含调度循环。
"""

from __future__ import annotations

import logging

from app.core.deps import async_session_factory
from app.services import process_instance_service as process_svc
from app.services.scan_scheduler import run_scan_once

logger = logging.getLogger(__name__)

TIANDI_SCAN_TARGET = "tiandy.scan_pending"
TIANDI_SIGN_POLL_TARGET = "tiandy.sign_poll"


async def scan_pending_due() -> None:
    created = await run_scan_once(async_session_factory, actor="timer:tiandy.scan_pending")
    logger.info("定时扫单到点：创建 %d 个扫单任务", created)


async def sign_poll_due() -> None:
    async with async_session_factory() as db:
        result = await process_svc.run_sign_poll_once(db, actor="timer:tiandy.sign_poll")
    logger.info(
        "定时回签轮询到点：创建 %d 个探测任务（候选 %d）",
        result["created_count"],
        result["candidate_count"],
    )
