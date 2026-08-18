from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import bearer_scheme, get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.process import (
    ProcessInstanceDetail,
    ProcessInstanceListItem,
    ProcessLineDateSubmit,
    ProcessLineItemResponse,
    ProcessScanRequest,
    ProcessScanResponse,
    ProcessSignPollRunResponse,
    ProcessStageHistoryResponse,
)
from app.services import process_instance_service
from app.services.user_sync import resolve_login_username

router = APIRouter()


@router.get("", response_model=ApiResponse[list[ProcessInstanceListItem]])
async def list_process_instances(
    stage: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instances = await process_instance_service.list_instances(
        db, tenant_id, stage=stage, status=status, keyword=keyword
    )
    return ApiResponse(data=[ProcessInstanceListItem.model_validate(item) for item in instances])


@router.post("/scan", response_model=ApiResponse[ProcessScanResponse])
async def trigger_scan(
    body: ProcessScanRequest,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await process_instance_service.create_scan_task(
        db, tenant_id, body.portal_account_id, actor=user.user_id
    )
    return ApiResponse(data=ProcessScanResponse(task_id=task.id, status=task.status))


@router.post("/sign-poll/run-once", response_model=ApiResponse[ProcessSignPollRunResponse])
async def run_sign_poll_once(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    """立即跑一轮回签探测（不等待 30 分钟定时器）。"""
    require_tenant_access(user)
    result = await process_instance_service.run_sign_poll_once(db, actor=user.user_id)
    return ApiResponse(
        data=ProcessSignPollRunResponse(
            candidate_count=result["candidate_count"],
            created_count=result["created_count"],
        )
    )


@router.get("/{instance_id}", response_model=ApiResponse[ProcessInstanceDetail])
async def get_process_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await process_instance_service.get_instance(db, tenant_id, instance_id)
    lines = await process_instance_service.list_line_items(db, instance.id)
    history = await process_instance_service.list_stage_history(db, instance.id)
    sub_tasks = await process_instance_service.list_sub_tasks(db, instance.id)
    detail = ProcessInstanceDetail.model_validate(instance)
    detail.lines = [ProcessLineItemResponse.model_validate(line) for line in lines]
    detail.stage_history = [ProcessStageHistoryResponse.model_validate(item) for item in history]
    detail.sub_tasks = [
        process_instance_service.to_sub_task_response(task) for task in sub_tasks
    ]
    return ApiResponse(data=detail)


@router.post(
    "/{instance_id}/lines/{line_number}/date",
    response_model=ApiResponse[ProcessLineItemResponse],
)
async def submit_line_date(
    instance_id: str,
    line_number: str,
    body: ProcessLineDateSubmit,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    line = await process_instance_service.submit_line_date(
        db, tenant_id, instance_id, line_number, body.expected_delivery_date, user
    )
    return ApiResponse(data=ProcessLineItemResponse.model_validate(line))


@router.post("/{instance_id}/sign", response_model=ApiResponse[ProcessInstanceListItem])
async def request_sign(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await process_instance_service.request_sign(db, tenant_id, instance_id, user)
    return ApiResponse(data=ProcessInstanceListItem.model_validate(instance))


@router.post("/{instance_id}/archive", response_model=ApiResponse[ProcessInstanceListItem])
async def archive_signed_order(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    tenant_id = require_tenant_access(user)
    username = await resolve_login_username(
        credentials.credentials if credentials else None,
        user,
    )
    instance = await process_instance_service.archive_signed_order(
        db,
        tenant_id,
        instance_id,
        user,
        sdms_username=username,
    )
    return ApiResponse(data=ProcessInstanceListItem.model_validate(instance))


@router.post("/{instance_id}/retry", response_model=ApiResponse[ProcessInstanceListItem])
async def retry_process_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await process_instance_service.retry_instance(db, tenant_id, instance_id, user)
    return ApiResponse(data=ProcessInstanceListItem.model_validate(instance))


@router.post("/{instance_id}/cancel", response_model=ApiResponse[ProcessInstanceListItem])
async def cancel_process_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await process_instance_service.cancel_instance(db, tenant_id, instance_id, user)
    return ApiResponse(data=ProcessInstanceListItem.model_validate(instance))
