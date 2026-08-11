"""RPA worker registry."""

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.enums import WorkerStatus
from app.models.rpa_worker import RpaWorker
from app.schemas.dispatch import WorkerRegisterRequest
from app.services.json_utils import dumps_json


async def register_worker(db: AsyncSession, body: WorkerRegisterRequest) -> RpaWorker:
    now = datetime.now(UTC)
    existing = (
        await db.execute(
            select(RpaWorker).where(RpaWorker.worker_id == body.worker_id, not_deleted(RpaWorker))
        )
    ).scalar_one_or_none()
    if existing:
        existing.worker_type = body.worker_type
        existing.device_name = body.device_name
        existing.user_id = body.user_id
        existing.status = WorkerStatus.ONLINE
        existing.capabilities = dumps_json(body.capabilities)
        existing.app_version = body.app_version
        existing.agent_version = body.agent_version
        existing.os = body.os
        existing.last_heartbeat_at = now
        worker = existing
    else:
        worker = RpaWorker(
            worker_id=body.worker_id,
            worker_type=body.worker_type,
            device_name=body.device_name,
            user_id=body.user_id,
            status=WorkerStatus.ONLINE,
            capabilities=dumps_json(body.capabilities),
            app_version=body.app_version,
            agent_version=body.agent_version,
            os=body.os,
            last_heartbeat_at=now,
        )
        db.add(worker)
    await db.commit()
    await db.refresh(worker)
    return worker


async def heartbeat_worker(db: AsyncSession, worker_id: str) -> RpaWorker:
    worker = (
        await db.execute(
            select(RpaWorker).where(RpaWorker.worker_id == worker_id, not_deleted(RpaWorker))
        )
    ).scalar_one_or_none()
    if worker is None:
        raise NotFoundError(message="Worker 不存在", message_key="errors.autotask.worker_not_found")
    worker.last_heartbeat_at = datetime.now(UTC)
    worker.status = WorkerStatus.BUSY if worker.current_run_id else WorkerStatus.ONLINE
    await db.commit()
    await db.refresh(worker)
    return worker


async def list_workers(db: AsyncSession) -> list[RpaWorker]:
    result = await db.execute(
        select(RpaWorker).where(not_deleted(RpaWorker)).order_by(RpaWorker.last_heartbeat_at.desc())
    )
    return list(result.scalars().all())


async def get_worker(db: AsyncSession, worker_id: str) -> RpaWorker:
    worker = (
        await db.execute(
            select(RpaWorker).where(RpaWorker.worker_id == worker_id, not_deleted(RpaWorker))
        )
    ).scalar_one_or_none()
    if worker is None:
        raise NotFoundError(message="Worker 不存在", message_key="errors.autotask.worker_not_found")
    return worker


def worker_capabilities(worker: RpaWorker) -> list[str]:
    try:
        return json.loads(worker.capabilities or "[]")
    except json.JSONDecodeError:
        return []
