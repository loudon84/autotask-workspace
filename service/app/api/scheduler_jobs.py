"""调度中心：按 Binding 的定时任务列表/详情/任务日志。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.exceptions import NotFoundError
from app.core.security import (
    get_current_user,
    require_portal_manage_access,
    require_tenant_access,
)
from app.models.enums import PortalPermission
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.scheduler_job import (
    SchedulerJobResponse,
    SchedulerJobTaskItem,
    SchedulerJobTaskPage,
    SchedulerJobUpdate,
)
from app.services import audit_service
from app.services.audit_service import ACTION_SCHEDULER_JOB_UPDATED
from app.services import scheduler_job_service as job_svc
from app.services.permission_service import list_accessible_portal_ids

router = APIRouter()

SCHEDULER_JOB_RESOURCE_TYPE = "scheduler_job"


def _to_response(job, portal_name: str) -> SchedulerJobResponse:
    return SchedulerJobResponse(
        id=job.id,
        binding_id=job.binding_id,
        portal_account_id=job.portal_account_id,
        portal_name=portal_name,
        name=job.name,
        cron=job.cron,
        enabled=job.enabled,
        next_run_at=job_svc.next_run_at(job.cron, job.enabled),
    )


async def _visible_job_with_portal(
    db: AsyncSession, user: UserCache, tenant_id: str, job_id: str
) -> tuple:
    require_portal_manage_access(user)
    job, portal_name = await job_svc.get_scheduler_job_with_portal(db, job_id)
    accessible_ids = await list_accessible_portal_ids(
        db, user, tenant_id, PortalPermission.PORTAL_VIEW
    )
    if accessible_ids is not None and job.portal_account_id not in accessible_ids:
        raise NotFoundError(
            message="调度任务不存在",
            message_key="errors.autotask.scheduler_job_not_found",
        )
    return job, portal_name


@router.get("", response_model=ApiResponse[list[SchedulerJobResponse]])
async def list_scheduler_jobs(
    enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    require_portal_manage_access(user)
    tenant_id = require_tenant_access(user)
    accessible_ids = await list_accessible_portal_ids(
        db, user, tenant_id, PortalPermission.PORTAL_VIEW
    )
    rows = await job_svc.list_scheduler_jobs(
        db, accessible_portal_ids=accessible_ids, enabled=enabled
    )
    return ApiResponse(data=[_to_response(job, portal_name) for job, portal_name in rows])


@router.get("/{job_id}", response_model=ApiResponse[SchedulerJobResponse])
async def get_scheduler_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    job, portal_name = await _visible_job_with_portal(db, user, tenant_id, job_id)
    return ApiResponse(data=_to_response(job, portal_name))


@router.patch("/{job_id}", response_model=ApiResponse[SchedulerJobResponse])
async def patch_scheduler_job(
    job_id: str,
    body: SchedulerJobUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    job, portal_name = await _visible_job_with_portal(db, user, tenant_id, job_id)
    job = await job_svc.update_scheduler_job(
        db, job, enabled=body.enabled, cron=body.cron
    )
    await audit_service.write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=user.user_id,
        action=ACTION_SCHEDULER_JOB_UPDATED,
        resource_type=SCHEDULER_JOB_RESOURCE_TYPE,
        resource_id=job.id,
        details={"enabled": job.enabled, "cron": job.cron},
    )
    await db.commit()
    return ApiResponse(data=_to_response(job, portal_name), message="调度任务已更新")


@router.get("/{job_id}/tasks", response_model=ApiResponse[SchedulerJobTaskPage])
async def list_scheduler_job_tasks(
    job_id: str,
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    job, _portal_name = await _visible_job_with_portal(db, user, tenant_id, job_id)
    tasks, total = await job_svc.list_job_tasks(
        db, job, page=page, page_size=page_size
    )
    return ApiResponse(
        data=SchedulerJobTaskPage(
            items=[
                SchedulerJobTaskItem(
                    id=task.id,
                    title=task.title,
                    status=task.status,
                    created_at=task.created_at,
                )
                for task in tasks
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
    )
