"""Dashboard aggregation."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import TaskStatus, WorkerStatus
from app.models.rpa_worker import RpaWorker
from app.schemas.dashboard import DashboardStats, DashboardSummary, TaskTypeDistributionItem


async def get_dashboard_summary(db: AsyncSession, tenant_id: str) -> DashboardSummary:
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    tasks = (
        await db.execute(
            select(AutomationTask).where(
                AutomationTask.tenant_id == tenant_id,
                AutomationTask.created_at >= today_start,
                not_deleted(AutomationTask),
            )
        )
    ).scalars().all()

    today_total = len(tasks)
    pending = sum(1 for t in tasks if t.status in {TaskStatus.READY, TaskStatus.QUEUED})
    running = sum(1 for t in tasks if t.status in {TaskStatus.RUNNING, TaskStatus.LEASED})
    waiting_human = sum(
        1 for t in tasks if t.status in {TaskStatus.WAITING_HUMAN, TaskStatus.HUMAN_OPERATING}
    )
    failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    completed_today = sum(
        1
        for t in tasks
        if t.status in {TaskStatus.SUCCESS, TaskStatus.SUCCESS_MANUAL, TaskStatus.PARTIAL_SUCCESS}
    )
    success_rate = round(completed_today / max(today_total, 1) * 100, 2)

    heartbeat_cutoff = datetime.now(UTC) - timedelta(seconds=settings.WORKER_HEARTBEAT_TIMEOUT_SECONDS)
    online_workers = (
        await db.execute(
            select(func.count()).select_from(RpaWorker).where(
                RpaWorker.status.in_([WorkerStatus.ONLINE, WorkerStatus.BUSY]),
                RpaWorker.last_heartbeat_at >= heartbeat_cutoff,
                not_deleted(RpaWorker),
            )
        )
    ).scalar_one() or 0

    type_counter = Counter(t.task_type for t in tasks)
    task_type_distribution = [
        TaskTypeDistributionItem(task_type=task_type, count=count)
        for task_type, count in sorted(type_counter.items())
    ]

    return DashboardSummary(
        stats=DashboardStats(
            pending=pending,
            running=running,
            waiting_human=waiting_human,
            failed=failed,
            completed_today=completed_today,
            success_rate=success_rate,
            online_workers=online_workers,
        ),
        task_type_distribution=task_type_distribution,
    )
