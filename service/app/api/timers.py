"""调度中心：独立定时器列表/详情。响应不含门户、Binding、指向。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import (
    get_current_user,
    require_portal_manage_access,
    require_tenant_access,
)
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.timer import TimerResponse, TimerRunItem, TimerRunPage, TimerUpdate
from app.services import audit_service
from app.services import timer_registry
from app.services import timer_run_service as run_svc
from app.services import timer_service as timer_svc

router = APIRouter()

ACTION_TIMER_UPDATED = "timer.updated"
TIMER_RESOURCE_TYPE = "timer"


def _to_response(timer) -> TimerResponse:
    return TimerResponse(
        id=timer.id,
        name=timer.name,
        cron=timer.cron,
        enabled=timer.enabled,
        next_run_at=timer_svc.next_run_at(timer.cron, timer.enabled),
    )


@router.get("", response_model=ApiResponse[list[TimerResponse]])
async def list_timers(
    enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    require_portal_manage_access(user)
    require_tenant_access(user)
    rows = await timer_svc.list_timers(db, enabled=enabled)
    return ApiResponse(data=[_to_response(row) for row in rows])


@router.get("/{timer_id}", response_model=ApiResponse[TimerResponse])
async def get_timer(
    timer_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    require_portal_manage_access(user)
    require_tenant_access(user)
    timer = await timer_svc.get_timer(db, timer_id)
    return ApiResponse(data=_to_response(timer))


@router.patch("/{timer_id}", response_model=ApiResponse[TimerResponse])
async def patch_timer(
    timer_id: str,
    body: TimerUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    require_portal_manage_access(user)
    timer = await timer_svc.get_timer(db, timer_id)
    timer = await timer_svc.update_timer(
        db, timer, name=body.name, enabled=body.enabled, cron=body.cron
    )
    await audit_service.write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=user.user_id,
        action=ACTION_TIMER_UPDATED,
        resource_type=TIMER_RESOURCE_TYPE,
        resource_id=timer.id,
        details={"name": timer.name, "enabled": timer.enabled, "cron": timer.cron},
    )
    await db.commit()
    return ApiResponse(data=_to_response(timer), message="定时器已更新")


@router.get("/{timer_id}/runs", response_model=ApiResponse[TimerRunPage])
async def list_timer_runs(
    timer_id: str,
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    require_portal_manage_access(user)
    require_tenant_access(user)
    timer = await timer_svc.get_timer(db, timer_id)
    runs, total = await run_svc.list_runs(db, timer.id, page=page, page_size=page_size)
    return ApiResponse(
        data=TimerRunPage(
            items=[
                TimerRunItem(
                    id=run.id,
                    status=run.status,
                    triggered_at=run.triggered_at,
                    finished_at=run.finished_at,
                    error=run.error,
                )
                for run in runs
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


_RUN_MESSAGES = {
    "SUCCESS": "已执行成功",
    "FAILED": "执行失败",
    "NO_LISTENER": "已触发，但当前进程没有注册该入口",
}


@router.post("/{timer_id}/run", response_model=ApiResponse[TimerRunItem])
async def run_timer_now(
    timer_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    """立即执行一次：不看 enabled / cron，照常落执行记录。"""
    require_portal_manage_access(user)
    require_tenant_access(user)
    timer = await timer_svc.get_timer(db, timer_id)
    try:
        run = await run_svc.run_timer_now(db, timer)
    except ProgrammingError:
        # timer_runs 表未迁移：照常触发，不落记录
        from datetime import datetime

        now = datetime.now()
        try:
            had_listener = await timer_registry.notify(timer.target)
            status = "SUCCESS" if had_listener else "NO_LISTENER"
            error = None
        except Exception as exc:
            status, error = "FAILED", str(exc)[:500]
        return ApiResponse(
            data=TimerRunItem(
                id="", status=status, triggered_at=now, finished_at=now, error=error
            ),
            message=_RUN_MESSAGES[status] + "（记录表未迁移，未落记录）",
        )
    await db.commit()
    message = _RUN_MESSAGES.get(run.status, "已触发")
    if run.status == "FAILED" and run.error:
        message = f"执行失败：{run.error}"
    return ApiResponse(
        data=TimerRunItem(
            id=run.id,
            status=run.status,
            triggered_at=run.triggered_at,
            finished_at=run.finished_at,
            error=run.error,
        ),
        message=message,
    )
