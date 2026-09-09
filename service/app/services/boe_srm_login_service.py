"""京东方晨间登录：按账号去重后派薄登录 RPA，串行等待结果。"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.domain.boe_srm_login import BoeSrmLoginTarget
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import (
    BindingStatus,
    RunStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.portal_account import PortalAccount
from app.models.rpa_run import RpaRun
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json
from app.services.timer_registry import TimerBusinessError

logger = logging.getLogger(__name__)

LOGIN_TEMPLATE_CODE = "srm_boe_login"
LOGIN_WAIT_SECONDS = 180.0
LOGIN_POLL_SECONDS = 2.0
TERMINAL_RUN = {
    RunStatus.SUCCESS.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
    RunStatus.WAITING_HUMAN.value,
}

# @lat: [[domain#MailInbox]]


async def _find_login_binding(
    db: AsyncSession, tenant_id: str, portal_account_id: str
) -> WorkflowBinding | None:
    row = (
        await db.execute(
            select(WorkflowBinding, WorkflowTemplate)
            .join(
                WorkflowTemplate,
                WorkflowTemplate.id == WorkflowBinding.workflow_template_id,
            )
            .where(
                WorkflowTemplate.tenant_id == tenant_id,
                WorkflowTemplate.code == LOGIN_TEMPLATE_CODE,
                not_deleted(WorkflowTemplate),
                WorkflowBinding.portal_account_id == portal_account_id,
                WorkflowBinding.status == BindingStatus.ENABLED.value,
                not_deleted(WorkflowBinding),
            )
            .order_by(WorkflowBinding.created_at.desc())
            .limit(1)
        )
    ).first()
    return None if row is None else row[0]


async def wait_login_task(db: AsyncSession, task_id: str) -> tuple[str, str | None]:
    deadline = time.monotonic() + LOGIN_WAIT_SECONDS
    while time.monotonic() < deadline:
        run = (
            await db.execute(
                select(RpaRun)
                .where(RpaRun.task_id == task_id, not_deleted(RpaRun))
                .order_by(RpaRun.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if run is not None and run.status in TERMINAL_RUN:
            return run.status, run.error_message
        await db.rollback()
        await asyncio.sleep(LOGIN_POLL_SECONDS)
    return "TIMEOUT", "等待登录超时"


async def login_one_account(
    db: AsyncSession,
    *,
    tenant_id: str,
    portal: PortalAccount,
    target: BoeSrmLoginTarget,
    actor: str,
) -> str:
    if not (portal.credential_ref or "").strip():
        return "失败：门户未填密码"
    binding = await _find_login_binding(db, tenant_id, portal.id)
    if binding is None:
        return "失败：未绑定晨间登录 Flow"
    task = AutomationTask(
        tenant_id=tenant_id,
        title=f"京东方晨间登录 {target.login_account}",
        task_type=LOGIN_TEMPLATE_CODE,
        portal_account_id=portal.id,
        workflow_binding_id=binding.id,
        entity_type=portal.entity_type,
        erp_entity_code=portal.erp_entity_code,
        erp_entity_name=portal.erp_entity_name,
        status=TaskStatus.QUEUED.value,
        priority=TaskPriority.HIGH.value,
        input=dumps_json({"loginAccount": target.login_account}),
        created_by=actor,
        assigned_to=actor,
    )
    db.add(task)
    await db.flush()
    db.add(
        RpaRun(
            task_id=task.id,
            rpa_flow_id=binding.rpa_flow_id,
            status=RunStatus.QUEUED.value,
        )
    )
    await db.commit()
    status, err = await wait_login_task(db, task.id)
    if status == RunStatus.SUCCESS.value:
        return "成功"
    detail = (err or status or "失败").strip()
    if len(detail) > 80:
        detail = detail[:80]
    return f"失败：{detail}"


def summarize_login_wave(lines: list[str], *, any_fail: bool) -> str:
    summary = "；".join(lines) if lines else "没有可登录的京东方账号"
    summary = summary[:500]
    if any_fail or not lines:
        raise TimerBusinessError(summary)
    return summary
