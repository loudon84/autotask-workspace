"""定时器执行记录：到点落一条，结束回填状态与时刻。"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.timer import Timer
from app.models.timer_run import (
    TIMER_RUN_FAILED,
    TIMER_RUN_NO_LISTENER,
    TIMER_RUN_RUNNING,
    TIMER_RUN_SUCCESS,
    TimerRun,
)
from app.services import timer_registry


async def record_start(
    db: AsyncSession, *, timer_id: str, target: str, triggered_at: datetime
) -> TimerRun:
    run = TimerRun(
        timer_id=timer_id,
        target=target,
        status=TIMER_RUN_RUNNING,
        triggered_at=triggered_at,
    )
    db.add(run)
    await db.flush()
    return run


async def record_finish(
    db: AsyncSession,
    run: TimerRun,
    *,
    ok: bool,
    had_listener: bool = True,
    error: str | None = None,
    finished_at: datetime | None = None,
) -> TimerRun:
    if not had_listener:
        run.status = TIMER_RUN_NO_LISTENER
    else:
        run.status = TIMER_RUN_SUCCESS if ok else TIMER_RUN_FAILED
    run.error = error
    run.finished_at = finished_at or datetime.now()
    await db.flush()
    return run


async def run_timer_now(db: AsyncSession, timer: Timer) -> TimerRun:
    """立即执行一次：不受 enabled / cron 约束，照常落执行记录。"""
    run = await record_start(
        db, timer_id=timer.id, target=timer.target, triggered_at=datetime.now()
    )
    try:
        had_listener = await timer_registry.notify(timer.target)
    except Exception as exc:
        await record_finish(db, run, ok=False, error=str(exc)[:500])
        return run
    await record_finish(db, run, ok=True, had_listener=had_listener)
    return run


async def list_runs(
    db: AsyncSession, timer_id: str, *, page: int = 1, page_size: int = 20
) -> tuple[list[TimerRun], int]:
    base = select(TimerRun).where(
        TimerRun.timer_id == timer_id, not_deleted(TimerRun)
    )
    total = (
        await db.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()
    rows = (
        await db.execute(
            base.order_by(TimerRun.triggered_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(rows), total
