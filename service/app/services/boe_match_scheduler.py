"""京东方匹配交货计划：租户级定时器，不按门户扫 SRM。

开关与 cron 存 autotask_settings（scheduler_config_service），每个 tick 热加载；
.env 的 BOE_PACK_MATCH_JOB_* 仅作表中无值时的回退默认。不要挂 Binding
scheduler_jobs：一条租户级 HTTP 若按门户各绑一次会重复匹配。
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.portal_category import PortalCategory
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.services import boe_packing_service
from app.services import scheduler_config_service as config_svc
from app.services.cron_schedule import CronSchedule, seconds_until_due

logger = logging.getLogger(__name__)

_TICK_SECONDS = 30.0


# @lat: [[domain#SchedulerJob]]
class BoeMatchScheduler:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
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
        self._task = asyncio.create_task(self._run(), name="boe-pack-match-scheduler")

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
                if config.boe_pack_enabled:
                    self._apply_cron(config.boe_pack_cron)
                    now = datetime.now()
                    if self._next_fire is not None and now >= self._next_fire:
                        await self.process_once()
                        self._advance(now)
                        now = datetime.now()
                    wait_seconds = seconds_until_due(self._next_fire, now, _TICK_SECONDS)
                else:
                    self._schedule = None
                    self._next_fire = None
                    self._cron_text = None
            except Exception:
                logger.exception("京东方匹配交货计划调度失败")
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
        logger.info("京东方匹配计划已加载: %s（下次 %s）", cron_text, self._next_fire)

    def _advance(self, now: datetime) -> None:
        if self._schedule is not None:
            self._next_fire = self._schedule.next_after(now)

    async def process_once(self) -> int:
        async with self._session_factory() as db:
            tenants = list(
                (
                    await db.execute(
                        select(PortalAccount.tenant_id)
                        .where(
                            PortalAccount.category == PortalCategory.BOE.value,
                            not_deleted(PortalAccount),
                        )
                        .distinct()
                    )
                ).scalars().all()
            )
            created = 0
            for tenant_id in tenants:
                try:
                    result = await boe_packing_service.match_delivery_plans(
                        db, tenant_id, actor="boe-match-scheduler"
                    )
                    created += int(result.get("created_count") or 0)
                except Exception:
                    logger.exception("京东方匹配失败 tenant=%s", tenant_id)
                    await db.rollback()
            logger.info("京东方匹配完成: 新建 %d 单", created)
            return created
