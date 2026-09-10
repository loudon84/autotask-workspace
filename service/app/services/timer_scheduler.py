"""独立定时器调度：APScheduler 负责「到点」，30 秒协程只同步 timers 启用行。

timers 表存 crontab 5 段（dow 0/7=周日），交给框架前过 unix_cron 垫片。
开火仍只 notify(target)，timer_runs 留痕不变；本拍晚不超过 2 分钟仍算本拍
（misfire_grace_time=120），不补跑整拍；同一 target 不叠跑（max_instances=1）。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import timer_registry
from app.services import timer_run_service as run_svc
from app.services import timer_service as timer_svc
from app.services.china_clock import CHINA_TZ
from app.services.unix_cron import build_cron_trigger

logger = logging.getLogger(__name__)

_SYNC_SECONDS = 30.0
_MISFIRE_GRACE_SECONDS = 120


# @lat: [[domain#SchedulerJob]]
class TimerScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._scheduler = AsyncIOScheduler(timezone=CHINA_TZ)
        self._stop_event = asyncio.Event()
        self._sync_task: asyncio.Task[None] | None = None
        # 已挂上的 crontab 原文。同一 cron 不得每 30 秒 replace_existing，
        # 否则会重算 next_run_time，把 misfire_grace_time=120 冲掉。
        self._cron_by_id: dict[str, str] = {}

    async def start(self) -> None:
        if self._sync_task is not None and not self._sync_task.done():
            return
        self._stop_event.clear()
        self._scheduler.start()
        self._sync_task = asyncio.create_task(
            self._sync_loop(),
            name="timer-scheduler-sync",
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._sync_task is not None:
            await self._sync_task
            self._sync_task = None
        self._scheduler.shutdown(wait=False)

    async def _sync_loop(self) -> None:
        """每 30 秒把库里的开关/cron 同步进框架，不再自己判断是否到点。"""
        while not self._stop_event.is_set():
            try:
                await self._sync_once()
            except ProgrammingError:
                logger.warning("timers 表不存在，跳过本轮（迁库待授权）")
            except Exception:
                logger.exception("定时器同步失败")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=_SYNC_SECONDS)
            except TimeoutError:
                continue

    async def _sync_once(self) -> None:
        async with self._session_factory() as db:
            timers = await timer_svc.list_enabled_timers(db)
        active_ids: set[str] = set()
        for timer in timers:
            job_id = str(timer.id)
            try:
                trigger = build_cron_trigger(timer.cron)
            except ValueError:
                logger.warning("定时器 cron 非法 timer=%s cron=%s", timer.id, timer.cron)
                self._remove_job_quietly(job_id)
                continue
            active_ids.add(job_id)
            if (
                self._scheduler.get_job(job_id) is not None
                and self._cron_by_id.get(job_id) == timer.cron
            ):
                continue
            self._scheduler.add_job(
                self._fire,
                trigger=trigger,
                id=job_id,
                args=[job_id, timer.target],
                misfire_grace_time=_MISFIRE_GRACE_SECONDS,
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )
            self._cron_by_id[job_id] = timer.cron
            logger.info("定时器已加载: %s timer=%s", timer.cron, job_id)
        for job in self._scheduler.get_jobs():
            if job.id not in active_ids:
                self._remove_job_quietly(job.id)

    def _remove_job_quietly(self, job_id: str) -> None:
        self._cron_by_id.pop(job_id, None)
        if self._scheduler.get_job(job_id) is not None:
            self._scheduler.remove_job(job_id)

    async def _fire(self, timer_id: str, target: str) -> None:
        """到点：先落一条 RUNNING，notify 后回填结果；表未迁则只通知不落记录。"""
        triggered = datetime.now()
        try:
            async with self._session_factory() as db:
                run = await run_svc.record_start(
                    db, timer_id=timer_id, target=target, triggered_at=triggered
                )
                await db.commit()
                try:
                    had_listener, summary = await timer_registry.notify(target)
                except Exception as exc:
                    await run_svc.record_finish(db, run, ok=False, error=str(exc)[:500])
                    await db.commit()
                    logger.exception(
                        "定时器到期通知失败 timer=%s target=%s", timer_id, target
                    )
                    return
                await run_svc.record_finish(
                    db, run, ok=True, had_listener=had_listener, error=summary
                )
                await db.commit()
        except ProgrammingError:
            logger.warning("timer_runs 表不存在，本次到点不落记录（迁库待授权）")
            try:
                await timer_registry.notify(target)
            except Exception:
                logger.exception(
                    "定时器到期通知失败 timer=%s target=%s", timer_id, target
                )
