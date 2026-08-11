"""RPA run queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.rpa_run import RpaRun
from app.models.run_event import RunEvent
from app.models.step_run import StepRun


async def get_run(db: AsyncSession, tenant_id: str, run_id: str) -> RpaRun:
    run = (
        await db.execute(
            select(RpaRun)
            .join(AutomationTask, RpaRun.task_id == AutomationTask.id)
            .where(
                RpaRun.id == run_id,
                AutomationTask.tenant_id == tenant_id,
                not_deleted(RpaRun),
                not_deleted(AutomationTask),
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(message="Run 不存在", message_key="errors.autotask.run_not_found")
    return run


async def list_runs(db: AsyncSession, tenant_id: str, task_id: str | None = None) -> list[RpaRun]:
    query = (
        select(RpaRun)
        .join(AutomationTask, RpaRun.task_id == AutomationTask.id)
        .where(AutomationTask.tenant_id == tenant_id, not_deleted(RpaRun), not_deleted(AutomationTask))
    )
    if task_id:
        query = query.where(RpaRun.task_id == task_id)
    result = await db.execute(query.order_by(RpaRun.created_at.desc()))
    return list(result.scalars().all())


async def list_run_events(db: AsyncSession, tenant_id: str, run_id: str) -> list[RunEvent]:
    await get_run(db, tenant_id, run_id)
    result = await db.execute(
        select(RunEvent).where(RunEvent.run_id == run_id, not_deleted(RunEvent)).order_by(RunEvent.created_at.asc())
    )
    return list(result.scalars().all())


async def list_step_runs(db: AsyncSession, tenant_id: str, run_id: str) -> list[StepRun]:
    await get_run(db, tenant_id, run_id)
    result = await db.execute(
        select(StepRun).where(StepRun.run_id == run_id, not_deleted(StepRun)).order_by(StepRun.created_at.asc())
    )
    return list(result.scalars().all())
