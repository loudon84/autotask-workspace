"""独立定时器档案：列表/详情/改名称·开关·cron；启动时按登记插入缺失行。"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.base import not_deleted
from app.models.timer import Timer
from app.services.cron_schedule import CronParseError, CronSchedule
from app.services.timer_catalog import REGISTRATIONS, TimerRegistration


async def get_timer(db: AsyncSession, timer_id: str) -> Timer:
    row = (
        await db.execute(
            select(Timer).where(Timer.id == timer_id, not_deleted(Timer))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            message="定时器不存在",
            message_key="errors.autotask.timer_not_found",
        )
    return row


async def get_timer_by_target(db: AsyncSession, target: str) -> Timer | None:
    return (
        await db.execute(
            select(Timer).where(Timer.target == target, not_deleted(Timer))
        )
    ).scalar_one_or_none()


def next_run_at(
    cron: str, enabled: bool, now: datetime | None = None
) -> datetime | None:
    if not enabled:
        return None
    try:
        return CronSchedule.parse(cron).next_after(now or datetime.now())
    except CronParseError:
        return None


async def list_timers(
    db: AsyncSession, *, enabled: bool | None = None
) -> list[Timer]:
    stmt = select(Timer).where(not_deleted(Timer)).order_by(Timer.name.asc())
    if enabled is not None:
        stmt = stmt.where(Timer.enabled.is_(enabled))
    return list((await db.execute(stmt)).scalars().all())


async def list_enabled_timers(db: AsyncSession) -> list[Timer]:
    return await list_timers(db, enabled=True)


async def update_timer(
    db: AsyncSession,
    timer: Timer,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    cron: str | None = None,
) -> Timer:
    if cron is not None:
        cron_text = cron.strip()
        try:
            CronSchedule.parse(cron_text).next_after(datetime.now())
        except CronParseError as exc:
            raise UnprocessableError(
                message=f"非法 cron：{exc}",
                message_key="errors.autotask.invalid_schedule",
            ) from exc
        timer.cron = cron_text
    if name is not None:
        trimmed = name.strip()
        if not trimmed:
            raise UnprocessableError(
                message="名称不能为空",
                message_key="errors.autotask.timer_name_required",
            )
        timer.name = trimmed
    if enabled is not None:
        timer.enabled = enabled
    await db.flush()
    return timer


async def ensure_catalog_rows(
    db: AsyncSession,
    registrations: Sequence[TimerRegistration] | None = None,
) -> int:
    """按 target 插入缺失行；已存在不覆盖开关和 cron。"""
    items = REGISTRATIONS if registrations is None else registrations
    created = 0
    for item in items:
        existing = await get_timer_by_target(db, item.target)
        if existing is not None:
            continue
        db.add(
            Timer(
                target=item.target,
                name=item.name,
                cron=item.cron,
                enabled=item.enabled,
            )
        )
        created += 1
    if created:
        await db.flush()
    return created
