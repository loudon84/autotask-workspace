"""Scheduler jobs keyed by Binding id. config.schedule is first-insert only."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import BindingStatus
from app.models.portal_account import PortalAccount
from app.models.scheduler_job import SchedulerJob
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.binding_schedule import build_job_name, parse_schedule
from app.services.cron_schedule import CronParseError, CronSchedule
from app.services.process_instance_service import (
    CHECK_REPLY_TEMPLATE_CODE,
    SCAN_TASK_TYPE,
    create_scan_task,
    run_sign_poll_once,
)

logger = logging.getLogger(__name__)


async def get_job_by_binding_id(
    db: AsyncSession, binding_id: str
) -> SchedulerJob | None:
    return (
        await db.execute(
            select(SchedulerJob).where(
                SchedulerJob.binding_id == binding_id,
                not_deleted(SchedulerJob),
            )
        )
    ).scalar_one_or_none()


async def get_scheduler_job(db: AsyncSession, job_id: str) -> SchedulerJob:
    job = (
        await db.execute(
            select(SchedulerJob).where(
                SchedulerJob.id == job_id,
                not_deleted(SchedulerJob),
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError(
            message="调度任务不存在",
            message_key="errors.autotask.scheduler_job_not_found",
        )
    return job


async def get_scheduler_job_with_portal(
    db: AsyncSession, job_id: str
) -> tuple[SchedulerJob, str]:
    row = (
        await db.execute(
            select(SchedulerJob, PortalAccount.portal_name)
            .join(PortalAccount, PortalAccount.id == SchedulerJob.portal_account_id)
            .where(
                SchedulerJob.id == job_id,
                not_deleted(SchedulerJob),
                not_deleted(PortalAccount),
            )
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError(
            message="调度任务不存在",
            message_key="errors.autotask.scheduler_job_not_found",
        )
    return row[0], row[1]


async def sync_scheduler_job_from_binding(
    db: AsyncSession,
    *,
    binding: WorkflowBinding,
    portal: PortalAccount,
    config: dict[str, Any],
) -> SchedulerJob | None:
    """已有 job 则不覆盖 cron/name；Binding 停用则关掉 job。首次带 schedule 才插入。"""
    existing = await get_job_by_binding_id(db, binding.id)
    if existing is not None:
        if binding.status == BindingStatus.DISABLED:
            existing.enabled = False
        return existing
    decl = parse_schedule(config)
    if decl is None:
        return None
    job = SchedulerJob(
        binding_id=binding.id,
        portal_account_id=portal.id,
        name=build_job_name(portal.portal_name, decl.process_name, decl.action_name),
        cron=decl.cron,
        enabled=decl.enabled and binding.status == BindingStatus.ENABLED,
    )
    db.add(job)
    await db.flush()
    return job


async def disable_job_for_binding(db: AsyncSession, binding_id: str) -> None:
    job = await get_job_by_binding_id(db, binding_id)
    if job is not None:
        job.enabled = False


def next_run_at(cron: str, enabled: bool, now: datetime | None = None) -> datetime | None:
    if not enabled:
        return None
    try:
        return CronSchedule.parse(cron).next_after(now or datetime.now())
    except CronParseError:
        return None


async def list_scheduler_jobs(
    db: AsyncSession,
    *,
    accessible_portal_ids: list[str] | None,
    enabled: bool | None = None,
) -> list[tuple[SchedulerJob, str]]:
    stmt = (
        select(SchedulerJob, PortalAccount.portal_name)
        .join(PortalAccount, PortalAccount.id == SchedulerJob.portal_account_id)
        .where(not_deleted(SchedulerJob), not_deleted(PortalAccount))
        .order_by(SchedulerJob.name.asc())
    )
    if accessible_portal_ids is not None:
        if not accessible_portal_ids:
            return []
        stmt = stmt.where(SchedulerJob.portal_account_id.in_(accessible_portal_ids))
    if enabled is not None:
        stmt = stmt.where(SchedulerJob.enabled.is_(enabled))
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


async def list_enabled_jobs(db: AsyncSession) -> list[SchedulerJob]:
    return list(
        (
            await db.execute(
                select(SchedulerJob).where(
                    SchedulerJob.enabled.is_(True),
                    not_deleted(SchedulerJob),
                )
            )
        )
        .scalars()
        .all()
    )


async def update_scheduler_job(
    db: AsyncSession,
    job: SchedulerJob,
    *,
    enabled: bool | None,
    cron: str | None,
) -> SchedulerJob:
    if cron is not None:
        cron_text = cron.strip()
        try:
            CronSchedule.parse(cron_text)
        except CronParseError as exc:
            raise UnprocessableError(
                message=f"非法 cron：{exc}",
                message_key="errors.autotask.invalid_schedule",
            ) from exc
        job.cron = cron_text
    if enabled is not None:
        job.enabled = enabled
    await db.flush()
    return job


async def list_job_tasks(
    db: AsyncSession,
    job: SchedulerJob,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AutomationTask], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = (
        AutomationTask.workflow_binding_id == job.binding_id,
        not_deleted(AutomationTask),
    )
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(AutomationTask).where(*filters)
            )
        ).scalar_one()
    )
    rows = (
        (
            await db.execute(
                select(AutomationTask)
                .where(*filters)
                .order_by(AutomationTask.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def fire_scheduler_job(db: AsyncSession, job: SchedulerJob) -> None:
    binding = (
        await db.execute(
            select(WorkflowBinding).where(
                WorkflowBinding.id == job.binding_id,
                not_deleted(WorkflowBinding),
            )
        )
    ).scalar_one_or_none()
    if binding is None:
        logger.warning("调度任务开火跳过：Binding 不存在 job=%s", job.id)
        return
    template = (
        await db.execute(
            select(WorkflowTemplate).where(
                WorkflowTemplate.id == binding.workflow_template_id,
                not_deleted(WorkflowTemplate),
            )
        )
    ).scalar_one_or_none()
    if template is None:
        logger.warning("调度任务开火跳过：模板不存在 job=%s", job.id)
        return
    portal = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == job.portal_account_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if portal is None:
        logger.warning("调度任务开火跳过：门户不存在 job=%s", job.id)
        return
    code = template.code
    if code == SCAN_TASK_TYPE:
        task = await create_scan_task(
            db,
            portal.tenant_id,
            job.portal_account_id,
            actor="scheduler-job",
        )
        logger.info(
            "调度任务开火: %s 扫单已创建 task=%s job=%s",
            job.name,
            task.id,
            job.id,
        )
        return
    if code == CHECK_REPLY_TEMPLATE_CODE:
        result = await run_sign_poll_once(
            db,
            actor="scheduler-job",
            portal_account_id=job.portal_account_id,
        )
        logger.info(
            "调度任务开火: %s 回签轮询 创建 %s 个探测任务（候选 %s） job=%s",
            job.name,
            result["created_count"],
            result["candidate_count"],
            job.id,
        )
        return
    logger.info("调度任务开火忽略未支持模板 code=%s job=%s", code, job.id)
