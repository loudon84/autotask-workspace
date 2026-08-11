"""Phase 5 artifact upload / idempotency tests."""

import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")
os.environ.setdefault("ARTIFACT_STORAGE", "local")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError
from app.schemas.dispatch import RunArtifactCreate, WorkerArtifactUploadUrlRequest
from app.schemas.resource import ArtifactUploadUrlRequest
from app.services import artifact_service, dispatch_service, s3_storage


def test_build_storage_key_isolates_tenant_task_run():
    key = artifact_service.build_storage_key("tenant-a", "task-1", "run-1", "shot.png")
    assert key == "tenant-a/task-1/run-1/shot.png"


def test_artifact_upload_request_accepts_snake_case():
    body = ArtifactUploadUrlRequest.model_validate(
        {"task_id": "task-1", "run_id": "run-1", "name": "a.png", "mime_type": "image/png"}
    )
    assert body.task_id == "task-1"
    assert body.run_id == "run-1"


def test_worker_upload_request_accepts_snake_case():
    body = WorkerArtifactUploadUrlRequest.model_validate(
        {
            "worker_id": "server-worker-001",
            "task_id": "task-1",
            "run_id": "run-1",
            "name": "trace.zip",
        }
    )
    assert body.worker_id == "server-worker-001"


@pytest.mark.asyncio
async def test_append_run_artifact_idempotent():
    run = MagicMock()
    run.id = "run-1"
    run.task_id = "task-1"

    task = MagicMock()
    task.id = "task-1"
    task.tenant_id = "tenant-1"

    existing = MagicMock()
    existing.id = "art-1"

    db = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "rpa_runs" in sql.lower() or "RpaRun" in sql:
            result.scalar_one_or_none.return_value = run
            return result
        if "automation_tasks" in sql.lower() or "AutomationTask" in sql:
            result.scalar_one_or_none.return_value = task
            return result
        result.scalar_one_or_none.return_value = existing
        return result

    db.execute = AsyncMock(side_effect=_execute)
    db.commit = AsyncMock()

    with patch.object(dispatch_service, "find_artifact_by_storage_key", AsyncMock(return_value=existing)):
        with patch.object(dispatch_service, "create_artifact_record", AsyncMock()) as create_mock:
            await dispatch_service.append_run_artifact(
                db,
                "run-1",
                RunArtifactCreate(
                    type="SCREENSHOT",
                    name="a.png",
                    storage_key="tenant-1/task-1/run-1/a.png",
                    size=10,
                ),
                created_by=None,
            )
            create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_append_run_artifact_rejects_out_of_scope_key():
    run = MagicMock()
    run.id = "run-1"
    run.task_id = "task-1"

    task = MagicMock()
    task.id = "task-1"
    task.tenant_id = "tenant-1"

    db = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "rpa_runs" in sql.lower() or "RpaRun" in sql:
            result.scalar_one_or_none.return_value = run
            return result
        result.scalar_one_or_none.return_value = task
        return result

    db.execute = AsyncMock(side_effect=_execute)

    with pytest.raises(BadRequestError) as exc:
        await dispatch_service.append_run_artifact(
            db,
            "run-1",
            RunArtifactCreate(
                type="SCREENSHOT",
                name="a.png",
                storage_key="other-tenant/task-x/run-y/a.png",
                size=10,
            ),
            created_by=None,
        )
    assert exc.value.message_key == "errors.autotask.storage_key_out_of_scope"


def test_create_upload_target_local():
    url = s3_storage.create_upload_target("tenant/task/run/file.png", "image/png")
    assert "artifacts/upload/" in url


def test_local_artifact_urls_use_separate_configured_bases():
    with (
        patch.object(s3_storage.settings, "ARTIFACT_UPLOAD_BASE_URL", "http://127.0.0.1:4520/"),
        patch.object(s3_storage.settings, "ARTIFACT_DOWNLOAD_BASE_URL", "http://download.example:4520/"),
    ):
        upload_url = s3_storage.local_upload_url("tenant/task/run/file.png")
        download_url = s3_storage.local_download_url("tenant/task/run/file.png")

    assert upload_url.startswith("http://127.0.0.1:4520/api/v1/autotask/artifacts/upload/")
    assert download_url.startswith("http://download.example:4520/api/v1/autotask/artifacts/download/")


def test_local_artifact_urls_fall_back_to_public_base_url():
    with (
        patch.object(s3_storage.settings, "PUBLIC_BASE_URL", "http://fallback.example:4520/"),
        patch.object(s3_storage.settings, "ARTIFACT_UPLOAD_BASE_URL", ""),
        patch.object(s3_storage.settings, "ARTIFACT_DOWNLOAD_BASE_URL", ""),
    ):
        upload_url = s3_storage.local_upload_url("tenant/task/run/file.png")
        download_url = s3_storage.local_download_url("tenant/task/run/file.png")

    assert upload_url.startswith("http://fallback.example:4520/api/v1/autotask/artifacts/upload/")
    assert download_url.startswith("http://fallback.example:4520/api/v1/autotask/artifacts/download/")


@pytest.mark.asyncio
async def test_create_worker_upload_url_checks_run_belongs_to_task():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(Exception):
        await artifact_service.create_worker_upload_url(
            db,
            WorkerArtifactUploadUrlRequest(
                worker_id="w1",
                task_id="task-1",
                run_id="run-missing",
                name="a.png",
            ),
        )
