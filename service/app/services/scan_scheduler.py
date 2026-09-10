"""天地伟业定时扫单：为已启用扫单 Binding 的门户建扫单任务。

开关与 cron 在调度中心 `timers`（`tiandy.scan_pending`）。本模块只有到点入口
要调用的 `run_scan_once`，不再自带循环。
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.portal_category import PortalCategory
from app.models.base import not_deleted
from app.models.enums import PortalAccountStatus
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.process_instance_service import SCAN_TASK_TYPE, create_scan_task

logger = logging.getLogger(__name__)


async def run_scan_once(
    session_factory: async_sessionmaker[AsyncSession], *, actor: str
) -> int:
    """为每个「已启用扫单绑定」的天地伟业门户创建一个扫单子任务。"""
    now = datetime.now()
    async with session_factory() as db:
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
                        PortalAccount.category == PortalCategory.TIANDI.value,
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
                    actor=actor,
                )
                created += 1
            except Exception:
                logger.exception("扫单任务创建失败: portal=%s", portal.id)
                await db.rollback()
        logger.info("扫单调度完成: 创建 %d 个扫单任务（%s）", created, now.isoformat())
        return created
