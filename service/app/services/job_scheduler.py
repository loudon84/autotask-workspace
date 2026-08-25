"""按 Binding 调度任务循环：一条 job 一个 cron，到点按门户开火。

复用现有醒法：seconds_until_due(next_fire, now, max_wait=30)。
cron 变更则重算下次触发且不补跑上一拍。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import scheduler_job_service as job_svc
from app.services.cron_schedule import CronParseError, CronSchedule, seconds_until_due

logger = logging.getLogger(__name__)

_TICK_SECONDS = 30.0


class JobScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings=None,
    ) -> None:
        self._session_factory = session_factory
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._next_fire: dict[str, datetime] = {}
        self._cron_text: dict[str, str] = {}
        self._schedules: dict[str, CronSchedule] = {}

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="binding-job-scheduler")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            wait_seconds = _TICK_SECONDS
            try:
                wait_seconds = await self._tick()
            except Exception:
                logger.exception("Binding 调度循环失败")
            if wait_seconds <= 0:
                continue
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait_seconds)
            except TimeoutError:
                continue

    async def _tick(self) -> float:
        async with self._session_factory() as db:
            jobs = await job_svc.list_enabled_jobs(db)
        now = datetime.now()
        active_ids = {job.id for job in jobs}
        for stale_id in list(self._next_fire):
            if stale_id not in active_ids:
                self._next_fire.pop(stale_id, None)
                self._cron_text.pop(stale_id, None)
                self._schedules.pop(stale_id, None)

        due_jobs = []
        wait_seconds = _TICK_SECONDS
        for job in jobs:
            self._apply_job_cron(job, now)
            next_fire = self._next_fire.get(job.id)
            if next_fire is not None and now >= next_fire:
                due_jobs.append(job)
            wait_seconds = min(
                wait_seconds,
                seconds_until_due(next_fire, now, _TICK_SECONDS),
            )

        for job in due_jobs:
            try:
                async with self._session_factory() as db:
                    live = await job_svc.get_scheduler_job(db, job.id)
                    if not live.enabled:
                        continue
                    await job_svc.fire_scheduler_job(db, live)
            except Exception:
                logger.exception("调度任务开火失败 job=%s", job.id)
            now = datetime.now()
            self._advance(job.id, now)
            wait_seconds = min(
                wait_seconds,
                seconds_until_due(self._next_fire.get(job.id), now, _TICK_SECONDS),
            )
        return wait_seconds

    def _apply_job_cron(self, job, now: datetime) -> None:
        if job.cron == self._cron_text.get(job.id):
            return
        try:
            schedule = CronSchedule.parse(job.cron)
        except CronParseError:
            logger.warning("调度任务 cron 非法 job=%s cron=%s", job.id, job.cron)
            self._cron_text[job.id] = job.cron
            self._next_fire.pop(job.id, None)
            self._schedules.pop(job.id, None)
            return
        self._cron_text[job.id] = job.cron
        self._schedules[job.id] = schedule
        self._next_fire[job.id] = schedule.next_after(now)
        logger.info(
            "调度计划已加载: %s job=%s（下次 %s）",
            job.cron,
            job.id,
            self._next_fire[job.id],
        )

    def _advance(self, job_id: str, now: datetime) -> None:
        schedule = self._schedules.get(job_id)
        if schedule is not None:
            self._next_fire[job_id] = schedule.next_after(now)
