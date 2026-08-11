from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.exceptions import ForbiddenError
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.resource import (
    ArtifactDownloadUrlResponse,
    ArtifactResponse,
    ArtifactUploadUrlRequest,
    ArtifactUploadUrlResponse,
)
from app.services import artifact_service

router = APIRouter()


@router.get("", response_model=ApiResponse[list[ArtifactResponse]])
async def list_artifacts(
    task_id: str | None = Query(None, alias="taskId"),
    run_id: str | None = Query(None, alias="runId"),
    task_id_snake: str | None = Query(None, alias="task_id"),
    run_id_snake: str | None = Query(None, alias="run_id"),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    resolved_task_id = task_id or task_id_snake
    resolved_run_id = run_id or run_id_snake
    artifacts = await artifact_service.list_artifacts(
        db, tenant_id, task_id=resolved_task_id, run_id=resolved_run_id
    )
    return ApiResponse(data=[ArtifactResponse.model_validate(a) for a in artifacts])


@router.get("/{artifact_id}", response_model=ApiResponse[ArtifactResponse])
async def get_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    artifact = await artifact_service.get_artifact(db, tenant_id, artifact_id)
    return ApiResponse(data=ArtifactResponse.model_validate(artifact))


@router.get("/{artifact_id}/download-url", response_model=ApiResponse[ArtifactDownloadUrlResponse])
async def get_download_url(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    artifact = await artifact_service.get_artifact(db, tenant_id, artifact_id)
    return ApiResponse(data=ArtifactDownloadUrlResponse(url=artifact_service.get_download_url(artifact.storage_key)))


@router.post("/upload-url", response_model=ApiResponse[ArtifactUploadUrlResponse])
async def create_upload_url(
    body: ArtifactUploadUrlRequest,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    upload_url, storage_key = await artifact_service.create_upload_url(db, tenant_id, user, body)
    return ApiResponse(data=ArtifactUploadUrlResponse(upload_url=upload_url, storage_key=storage_key))


@router.put("/upload/{storage_key:path}")
async def upload_artifact_local(storage_key: str, request: Request):
    body = await request.body()
    file_path = Path(artifact_service._artifact_root()) / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(body)
    return ApiResponse(data={"storageKey": storage_key, "size": len(body)}, message="上传成功")


@router.get("/download/{storage_key:path}")
async def download_artifact(storage_key: str, expires: int, sig: str):
    if not artifact_service.verify_download_signature(storage_key, expires, sig):
        raise ForbiddenError(message="下载链接无效或已过期", message_key="errors.autotask.download_invalid")
    file_path = Path(artifact_service._artifact_root()) / storage_key
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"error_code": 40400, "message_key": "errors.autotask.artifact_file_not_found", "message": "文件不存在"})
    return FileResponse(file_path)
