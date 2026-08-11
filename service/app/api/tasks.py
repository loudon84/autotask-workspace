from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.resource import ArtifactResponse, HumanActionResponse, RpaRunResponse
from app.schemas.task import (
    AutomationTaskCreate,
    AutomationTaskResponse,
    AutomationTaskUpdate,
    TaskConfirmHumanResponse,
    TaskHumanActionStatusResponse,
    TaskListItemResponse,
    TaskListPageResponse,
    TaskMessageResponse,
    TaskSuccessorJobResponse,
)
from app.services import (
    artifact_service,
    automation_task_service,
    human_action_service,
    task_successor_service,
    task_view_service,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[list[TaskListItemResponse] | TaskListPageResponse])
async def list_tasks(
    status: str | None = None,
    customer_name: str | None = Query(None, alias="customerName"),
    task_type: str | None = Query(None, alias="taskType"),
    workflow_template_id: str | None = Query(None, alias="workflowTemplateId"),
    priority: str | None = None,
    owner: str | None = None,
    keyword: str | None = None,
    page: int | None = None,
    page_size: int | None = Query(None, alias="pageSize"),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    result = await task_view_service.list_tasks_for_frontend(
        db,
        tenant_id,
        status=status,
        customer_name=customer_name,
        task_type=task_type,
        workflow_template_id=workflow_template_id,
        priority=priority,
        owner=owner,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(data=result)


@router.post("", response_model=ApiResponse[AutomationTaskResponse])
async def create_task(
    body: AutomationTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.create_task(db, tenant_id, user, body)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.get("/{task_id}", response_model=ApiResponse[TaskListItemResponse])
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.get_task(db, tenant_id, task_id)
    item = await task_view_service.build_task_list_item_for_task(db, tenant_id, task)
    return ApiResponse(data=item)


@router.get("/{task_id}/human-action", response_model=ApiResponse[HumanActionResponse | None])
async def get_task_human_action(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    action = await human_action_service.get_active_human_action_for_task(db, tenant_id, task_id)
    if action is None:
        return ApiResponse(data=None)
    return ApiResponse(data=HumanActionResponse.model_validate(action))


@router.post("/{task_id}/human-opened", response_model=ApiResponse[TaskHumanActionStatusResponse])
async def mark_task_human_opened(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    _action, task = await human_action_service.open_human_action_for_task(db, tenant_id, task_id, user)
    return ApiResponse(data=TaskHumanActionStatusResponse(task_id=task.id, status=task.status))


@router.post("/{task_id}/confirm-human", response_model=ApiResponse[TaskConfirmHumanResponse])
async def confirm_task_human(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    action, task = await human_action_service.confirm_human_action_for_task(db, tenant_id, task_id, user)
    return ApiResponse(
        data=TaskConfirmHumanResponse(
            task_id=task.id,
            status=task.status,
            confirmed_at=action.confirmed_at,
        )
    )


@router.patch("/{task_id}", response_model=ApiResponse[AutomationTaskResponse])
async def update_task(
    task_id: str,
    body: AutomationTaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.update_task(db, tenant_id, task_id, body)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/submit", response_model=ApiResponse[AutomationTaskResponse])
async def submit_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.submit_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/start", response_model=ApiResponse[AutomationTaskResponse])
async def start_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.start_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/cancel", response_model=ApiResponse[AutomationTaskResponse])
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.cancel_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/retry", response_model=ApiResponse[AutomationTaskResponse])
async def retry_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.retry_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/mark-success-manual", response_model=ApiResponse[AutomationTaskResponse])
async def mark_success_manual(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.mark_success_manual(db, tenant_id, task_id, user)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.get("/{task_id}/messages", response_model=ApiResponse[list[TaskMessageResponse]])
async def list_task_messages(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    messages = await automation_task_service.list_task_messages(db, tenant_id, task_id)
    return ApiResponse(data=[TaskMessageResponse.model_validate(m) for m in messages])


@router.get("/{task_id}/runs", response_model=ApiResponse[list[RpaRunResponse]])
async def list_task_runs(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    runs = await automation_task_service.list_task_runs(db, tenant_id, task_id)
    return ApiResponse(data=[RpaRunResponse.model_validate(r) for r in runs])


@router.get(
    "/{task_id}/successors",
    response_model=ApiResponse[list[TaskSuccessorJobResponse]],
)
async def list_task_successors(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await automation_task_service.get_task(db, tenant_id, task_id)
    jobs = await task_successor_service.list_successor_jobs(
        db,
        tenant_id=tenant_id,
        source_task_id=task_id,
    )
    return ApiResponse(
        data=[TaskSuccessorJobResponse.model_validate(job) for job in jobs]
    )


@router.post(
    "/{task_id}/successors/{job_id}/retry",
    response_model=ApiResponse[TaskSuccessorJobResponse],
)
async def retry_task_successor(
    task_id: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await automation_task_service.get_task(db, tenant_id, task_id)
    job = await task_successor_service.retry_successor_job(
        db,
        tenant_id=tenant_id,
        source_task_id=task_id,
        job_id=job_id,
    )
    return ApiResponse(data=TaskSuccessorJobResponse.model_validate(job))


@router.get("/{task_id}/artifacts", response_model=ApiResponse[list[ArtifactResponse]])
async def list_task_artifacts(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    artifacts = await artifact_service.list_artifacts(db, tenant_id, task_id=task_id)
    return ApiResponse(data=[ArtifactResponse.model_validate(a) for a in artifacts])
