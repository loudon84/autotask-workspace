"""SRM 待回签/待签章回签轮询调度器。

每 SIGN_POLL_INTERVAL_SECONDS（默认 1800）为 ACTIVE 且阶段为
SIGN_REQUESTED（待回签）或 DATES_COMPLETE（待签章，演示 TEMP）的流程实例
创建回签探测子任务；探测 Flow 成功且 replyStatus=已回签 时由 finish_run 钩子自动归档。
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.services import process_instance_service as svc

logger = logging.getLogger(__name__)


class SignPollScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._interval = settings.SIGN_POLL_INTERVAL_SECONDS
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="srm-sign-poll-scheduler")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.process_once()
            except Exception:
                logger.exception("回签轮询调度失败")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except TimeoutError:
                continue

    async def process_once(self) -> int:
        async with self._session_factory() as db:
            result = await svc.run_sign_poll_once(db, actor="sign-poll-scheduler")
            created = int(result["created_count"])
            logger.info(
                "回签轮询完成: 创建 %d 个探测任务（候选 %d）",
                created,
                result["candidate_count"],
            )
            return created
