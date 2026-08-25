"""SRM 待回签/待签章回签轮询调度器。

为 ACTIVE 且阶段为 SIGN_REQUESTED（待回签）或 DATES_COMPLETE（待签章，演示 TEMP）
的流程实例创建回签探测子任务；探测 Flow 成功且 replyStatus=已回签 时由 finish_run 钩子自动归档。

开关与触发时刻存 autotask_settings 表（scheduler_config_service），cron 表达式
（如 `*/30 * * * *` 每半小时）本地时间触发，每个 tick 重新读取热生效；
.env 的 SIGN_POLL_* 仅作表中无值时的回退默认。
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import process_instance_service as svc
from app.services import scheduler_config_service as config_svc
from app.services.cron_schedule import CronSchedule, seconds_until_due

logger = logging.getLogger(__name__)

# 配置热加载轮询上限（秒）；到点附近会按剩余秒数提前醒，不会再拖半分钟
_TICK_SECONDS = 30.0


class SignPollScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings=None,
    ) -> None:
        self._session_factory = session_factory
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._cron_text: str | None = None
        self._schedule: CronSchedule | None = None
        self._next_fire: datetime | None = None

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
            wait_seconds = _TICK_SECONDS
            try:
                async with self._session_factory() as db:
                    config = await config_svc.get_scheduler_config(db)
                if config.sign_poll_enabled:
                    self._apply_cron(config.sign_poll_cron)
                    now = datetime.now()
                    if self._next_fire is not None and now >= self._next_fire:
                        await self.process_once()
                        self._advance(now)
                        now = datetime.now()
                    wait_seconds = seconds_until_due(
                        self._next_fire, now, _TICK_SECONDS
                    )
                else:
                    self._schedule = None
                    self._next_fire = None
                    self._cron_text = None
            except Exception:
                logger.exception("回签轮询调度失败")
            if wait_seconds <= 0:
                continue
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait_seconds)
            except TimeoutError:
                continue

    def _apply_cron(self, cron_text: str) -> None:
        if cron_text == self._cron_text:
            return
        self._cron_text = cron_text
        self._schedule = CronSchedule.parse(cron_text)
        self._advance(datetime.now())
        logger.info("回签轮询计划已加载: %s（下次 %s）", cron_text, self._next_fire)

    def _advance(self, now: datetime) -> None:
        if self._schedule is not None:
            self._next_fire = self._schedule.next_after(now)

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
