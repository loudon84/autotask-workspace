from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.dispatch import (
    RunArtifactCreate,
    RunEventCreate,
    RunFinishRequest,
    WorkerArtifactUploadUrlRequest,
    WorkerLeaseRenewRequest,
    WorkerLeaseRenewResponse,
    WorkerLeaseRequest,
    WorkerLeaseResponse,
    WorkerRegisterRequest,
)
from app.schemas.resource import ArtifactUploadUrlResponse, RpaRunResponse, RpaWorkerResponse, RunEventResponse
from app.services import artifact_service, dispatch_service, rpa_worker_service

router = APIRouter()


def _to_worker_response(worker) -> RpaWorkerResponse:
    return RpaWorkerResponse(
        id=worker.worker_id,
        worker_type=worker.worker_type,
        device_name=worker.device_name,
        user_id=worker.user_id,
        status=worker.status,
        capabilities=rpa_worker_service.worker_capabilities(worker),
        app_version=worker.app_version,
        agent_version=worker.agent_version,
        os=worker.os,
        current_run_id=worker.current_run_id,
        last_heartbeat_at=worker.last_heartbeat_at,
    )


@router.post("/workers/register", response_model=ApiResponse[RpaWorkerResponse])
async def register_worker(body: WorkerRegisterRequest, db: AsyncSession = Depends(get_db)):
    worker = await rpa_worker_service.register_worker(db, body)
    return ApiResponse(data=_to_worker_response(worker))


@router.post("/workers/{worker_id}/heartbeat", response_model=ApiResponse[RpaWorkerResponse])
async def heartbeat_worker(worker_id: str, db: AsyncSession = Depends(get_db)):
    worker = await rpa_worker_service.heartbeat_worker(db, worker_id)
    return ApiResponse(data=_to_worker_response(worker))


@router.post("/tasks/lease", response_model=ApiResponse[WorkerLeaseResponse | None])
async def lease_task(body: WorkerLeaseRequest, db: AsyncSession = Depends(get_db)):
    lease = await dispatch_service.lease_task(db, body)
    return ApiResponse(data=lease)


@router.post("/tasks/{task_id}/lease/renew", response_model=ApiResponse[WorkerLeaseRenewResponse])
async def renew_lease(task_id: str, body: WorkerLeaseRenewRequest, db: AsyncSession = Depends(get_db)):
    data = await dispatch_service.renew_lease(db, task_id, body)
    return ApiResponse(data=data, message="续租成功")


@router.post("/artifacts/upload-url", response_model=ApiResponse[ArtifactUploadUrlResponse])
async def create_worker_upload_url(body: WorkerArtifactUploadUrlRequest, db: AsyncSession = Depends(get_db)):
    upload_url, storage_key = await artifact_service.create_worker_upload_url(db, body)
    return ApiResponse(data=ArtifactUploadUrlResponse(upload_url=upload_url, storage_key=storage_key))


@router.post("/runs/{run_id}/events", response_model=ApiResponse[RunEventResponse])
async def create_run_event(run_id: str, body: RunEventCreate, db: AsyncSession = Depends(get_db)):
    event = await dispatch_service.append_run_event(db, run_id, body)
    return ApiResponse(data=RunEventResponse.model_validate(event))


@router.post("/runs/{run_id}/artifacts", response_model=ApiResponse[None])
async def create_run_artifact(
    run_id: str, body: RunArtifactCreate, db: AsyncSession = Depends(get_db)
):
    await dispatch_service.append_run_artifact(db, run_id, body, created_by=None)
    return ApiResponse(data=None, message="Artifact 已记录")


@router.post("/runs/{run_id}/finish", response_model=ApiResponse[RpaRunResponse])
async def finish_run(run_id: str, body: RunFinishRequest, db: AsyncSession = Depends(get_db)):
    run = await dispatch_service.finish_run(db, run_id, body)
    return ApiResponse(data=RpaRunResponse.model_validate(run))
