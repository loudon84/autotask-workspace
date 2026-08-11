from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.resource import RpaRunResponse, RunEventResponse, StepRunResponse
from app.services import rpa_run_service

router = APIRouter()


@router.get("", response_model=ApiResponse[list[RpaRunResponse]])
async def list_runs(
    task_id: str | None = Query(None, alias="taskId"),
    task_id_snake: str | None = Query(None, alias="task_id"),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    runs = await rpa_run_service.list_runs(db, tenant_id, task_id=task_id or task_id_snake)
    return ApiResponse(data=[RpaRunResponse.model_validate(r) for r in runs])


@router.get("/{run_id}", response_model=ApiResponse[RpaRunResponse])
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    run = await rpa_run_service.get_run(db, tenant_id, run_id)
    return ApiResponse(data=RpaRunResponse.model_validate(run))


@router.get("/{run_id}/events", response_model=ApiResponse[list[RunEventResponse]])
async def list_run_events(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    events = await rpa_run_service.list_run_events(db, tenant_id, run_id)
    return ApiResponse(data=[RunEventResponse.model_validate(e) for e in events])


@router.get("/{run_id}/step-runs", response_model=ApiResponse[list[StepRunResponse]])
async def list_step_runs(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    steps = await rpa_run_service.list_step_runs(db, tenant_id, run_id)
    return ApiResponse(data=[StepRunResponse.model_validate(s) for s in steps])
