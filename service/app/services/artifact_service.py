"""Artifact storage and metadata."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.artifact import Artifact
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.rpa_run import RpaRun
from app.models.user_cache import UserCache
from app.schemas.dispatch import WorkerArtifactUploadUrlRequest
from app.schemas.resource import ArtifactUploadUrlRequest
from app.services import s3_storage


def build_storage_key(tenant_id: str, task_id: str, run_id: str | None, name: str) -> str:
    safe_name = name.replace("\\", "_").replace("/", "_")
    parts = [tenant_id, task_id]
    if run_id:
        parts.append(run_id)
    parts.append(safe_name)
    return "/".join(parts)


async def list_artifacts(
    db: AsyncSession,
    tenant_id: str,
    task_id: str | None = None,
    run_id: str | None = None,
) -> list[Artifact]:
    query = select(Artifact).where(Artifact.tenant_id == tenant_id, not_deleted(Artifact))
    if task_id:
        query = query.where(Artifact.task_id == task_id)
    if run_id:
        query = query.where(Artifact.run_id == run_id)
    result = await db.execute(query.order_by(Artifact.created_at.desc()))
    return list(result.scalars().all())


async def get_artifact(db: AsyncSession, tenant_id: str, artifact_id: str) -> Artifact:
    artifact = (
        await db.execute(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.tenant_id == tenant_id,
                not_deleted(Artifact),
            )
        )
    ).scalar_one_or_none()
    if artifact is None:
        raise NotFoundError(message="Artifact 不存在", message_key="errors.autotask.artifact_not_found")
    return artifact


async def create_upload_url(
    db: AsyncSession,
    tenant_id: str,
    user: UserCache,
    body: ArtifactUploadUrlRequest,
) -> tuple[str, str]:
    task = (
        await db.execute(
            select(AutomationTask).where(
                AutomationTask.id == body.task_id,
                AutomationTask.tenant_id == tenant_id,
                not_deleted(AutomationTask),
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    if body.run_id:
        run = (
            await db.execute(
                select(RpaRun).where(
                    RpaRun.id == body.run_id,
                    RpaRun.task_id == task.id,
                    not_deleted(RpaRun),
                )
            )
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundError(message="Run 不存在或不属于该任务", message_key="errors.autotask.run_not_found")

    storage_key = build_storage_key(tenant_id, body.task_id, body.run_id, body.name)
    upload_url = s3_storage.create_upload_target(storage_key, body.mime_type)
    return upload_url, storage_key


async def create_worker_upload_url(
    db: AsyncSession,
    body: WorkerArtifactUploadUrlRequest,
) -> tuple[str, str]:
    run = (
        await db.execute(
            select(RpaRun).where(
                RpaRun.id == body.run_id,
                RpaRun.task_id == body.task_id,
                not_deleted(RpaRun),
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(message="Run 不存在或不属于该任务", message_key="errors.autotask.run_not_found")
    if run.rpa_worker_id and run.rpa_worker_id != body.worker_id:
        raise NotFoundError(message="Worker 与 Run 不匹配", message_key="errors.autotask.worker_run_mismatch")

    task = (
        await db.execute(
            select(AutomationTask).where(AutomationTask.id == body.task_id, not_deleted(AutomationTask))
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    storage_key = build_storage_key(task.tenant_id, body.task_id, body.run_id, body.name)
    upload_url = s3_storage.create_upload_target(storage_key, body.mime_type)
    return upload_url, storage_key


def get_download_url(storage_key: str) -> str:
    return s3_storage.create_download_target(storage_key)


def verify_download_signature(storage_key: str, expires: int, sig: str) -> bool:
    return s3_storage.verify_local_download_signature(storage_key, expires, sig)


def _artifact_root():
    return s3_storage.local_artifact_root()


async def find_artifact_by_storage_key(db: AsyncSession, *, run_id: str, storage_key: str) -> Artifact | None:
    return (
        await db.execute(
            select(Artifact).where(
                Artifact.run_id == run_id,
                Artifact.storage_key == storage_key,
                not_deleted(Artifact),
            )
        )
    ).scalar_one_or_none()


async def create_artifact_record(
    db: AsyncSession,
    tenant_id: str,
    task_id: str,
    run_id: str | None,
    artifact_type: str,
    name: str,
    storage_key: str,
    size: int,
    mime_type: str | None,
    created_by: str | None,
) -> Artifact:
    artifact = Artifact(
        tenant_id=tenant_id,
        task_id=task_id,
        run_id=run_id,
        type=artifact_type,
        name=name,
        storage_key=storage_key,
        size=size,
        mime_type=mime_type,
        created_by=created_by,
    )
    db.add(artifact)
    await db.flush()
    return artifact
