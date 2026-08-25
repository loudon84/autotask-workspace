"""SRM 待签章订单定时扫单调度器。

按 cron 计划（如 `0 8 * * *` 每天 8 点、`0 8 * * 1-5` 工作日 8 点）为每个
"已启用扫单绑定"的 Portal 创建一个扫单子任务；扫单 Flow 成功后由 finish_run
钩子幂等创建流程实例。

只扫拥有 ENABLED 的 srm_scan_pending_orders 绑定的门户，避免对未配置扫单
Flow 的门户（如未来其他客户门户）误触发并刷错误日志。

开关与 cron 存 autotask_settings 表（scheduler_config_service），每个 tick
重新读取热生效；.env 的 SCAN_JOB_* 仅作表中无值时的回退默认。
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import not_deleted
from app.models.enums import PortalAccountStatus
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services import scheduler_config_service as config_svc
from app.services.cron_schedule import CronSchedule, seconds_until_due
from app.services.process_instance_service import SCAN_TASK_TYPE, create_scan_task

logger = logging.getLogger(__name__)

# 配置热加载轮询上限（秒）；到点附近会按剩余秒数提前醒，不会再拖半分钟
_TICK_SECONDS = 30.0


class ScanScheduler:
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
        self._task = asyncio.create_task(self._run(), name="srm-scan-scheduler")

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
                if config.scan_enabled:
                    self._apply_cron(config.scan_cron)
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
                logger.exception("扫单调度轮询失败")
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
        logger.info("扫单计划已加载: %s（下次 %s）", cron_text, self._next_fire)

    def _advance(self, now: datetime) -> None:
        if self._schedule is not None:
            self._next_fire = self._schedule.next_after(now)

    async def process_once(self) -> int:
        now = datetime.now()
        async with self._session_factory() as db:
            portals = list(
                (
                    await db.execute(
                        select(PortalAccount)
                        .join(
                            WorkflowBinding,
                            WorkflowBinding.portal_account_id == PortalAccount.id,
                        )
                        .join(
                            WorkflowTemplate,
                            WorkflowTemplate.id == WorkflowBinding.workflow_template_id,
                        )
                        .where(
                            PortalAccount.status == PortalAccountStatus.ENABLED.value,
                            not_deleted(PortalAccount),
                            WorkflowTemplate.code == SCAN_TASK_TYPE,
                            not_deleted(WorkflowTemplate),
                            WorkflowBinding.status == "ENABLED",
                            not_deleted(WorkflowBinding),
                        )
                    )
                )
                .scalars()
                .all()
            )
            created = 0
            for portal in portals:
                try:
                    await create_scan_task(
                        db,
                        portal.tenant_id,
                        portal.id,
                        actor="scan-scheduler",
                    )
                    created += 1
                except Exception:
                    logger.exception("扫单任务创建失败: portal=%s", portal.id)
                    await db.rollback()
            logger.info("扫单调度完成: 创建 %d 个扫单任务（%s）", created, now.isoformat())
            return created
