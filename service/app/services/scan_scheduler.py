"""SRM 待签章订单定时扫单调度器。

每天到点（SCAN_JOB_HOUR:SCAN_JOB_MINUTE，本地时间）为每个"已启用扫单绑定"
的 Portal 创建一个扫单子任务；扫单 Flow 成功后由 finish_run 钩子幂等创建流程实例。

只扫拥有 ENABLED 的 srm_scan_pending_orders 绑定的门户，避免对未配置扫单
Flow 的门户（如未来其他客户门户）误触发并刷错误日志。
"""

import asyncio
import logging
from datetime import datetime
from datetime import time as dt_time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models.base import not_deleted
from app.models.enums import PortalAccountStatus
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.process_instance_service import SCAN_TASK_TYPE, create_scan_task

logger = logging.getLogger(__name__)


class ScanScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._scan_time = dt_time(hour=settings.SCAN_JOB_HOUR, minute=settings.SCAN_JOB_MINUTE)
        self._poll_interval = settings.SCAN_JOB_POLL_INTERVAL_SECONDS
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._last_run_date: str | None = None

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
            try:
                await self.process_once()
            except Exception:
                logger.exception("扫单调度轮询失败")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
            except TimeoutError:
                continue

    async def process_once(self) -> int:
        now = datetime.now()
        today = now.date().isoformat()
        if self._last_run_date == today or now.time() < self._scan_time:
            return 0
        self._last_run_date = today
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
            logger.info("扫单调度完成: 创建 %d 个扫单任务", created)
            return created
