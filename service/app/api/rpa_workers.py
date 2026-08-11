from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.resource import RpaWorkerClientResponse
from app.services import rpa_worker_service

router = APIRouter()


def _to_worker_client_response(worker) -> RpaWorkerClientResponse:
    return RpaWorkerClientResponse(
        id=worker.worker_id,
        name=worker.device_name,
        status=worker.status,
        current_task_count=1 if worker.current_run_id else 0,
        browser_count=0,
        cpu_usage=0,
        memory_usage=0,
        last_heartbeat_at=worker.last_heartbeat_at,
    )


@router.get("", response_model=ApiResponse[list[RpaWorkerClientResponse]])
async def list_workers(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    workers = await rpa_worker_service.list_workers(db)
    return ApiResponse(data=[_to_worker_client_response(w) for w in workers])


@router.get("/{worker_id}", response_model=ApiResponse[RpaWorkerClientResponse])
async def get_worker(
    worker_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    worker = await rpa_worker_service.get_worker(db, worker_id)
    return ApiResponse(data=_to_worker_client_response(worker))
