"""调度器设置 API：读写 autotask_settings 中的扫单/回签轮询/京东方匹配 cron 配置。

修改后由调度器在下一个 tick 读取（最长约 30 秒生效），无需重启服务。
"""

from dataclasses import replace
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_portal_manage_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.setting import (
    SchedulerSettingsResponse,
    SchedulerSettingsUpdate,
)
from app.services import audit_service
from app.services import scheduler_config_service as config_svc
from app.services.cron_schedule import CronParseError, CronSchedule

router = APIRouter()

ACTION_SCHEDULER_SETTINGS_UPDATED = "settings.scheduler.updated"


def _next_run_iso(enabled: bool, cron: str) -> str | None:
    if not enabled:
        return None
    try:
        return CronSchedule.parse(cron).next_after(datetime.now()).isoformat()
    except CronParseError:
        return None


def _to_response(config: config_svc.SchedulerConfig) -> SchedulerSettingsResponse:
    next_run: dict[str, str | None] = {
        "sign_poll": _next_run_iso(config.sign_poll_enabled, config.sign_poll_cron),
        "scan": _next_run_iso(config.scan_enabled, config.scan_cron),
        "boe_pack": _next_run_iso(config.boe_pack_enabled, config.boe_pack_cron),
    }
    return SchedulerSettingsResponse(
        sign_poll={
            "enabled": config.sign_poll_enabled,
            "cron": config.sign_poll_cron,
        },
        scan={
            "enabled": config.scan_enabled,
            "cron": config.scan_cron,
        },
        boe_pack={
            "enabled": config.boe_pack_enabled,
            "cron": config.boe_pack_cron,
        },
        next_run_at=next_run,
    )


@router.get("/schedulers", response_model=ApiResponse[SchedulerSettingsResponse])
async def get_scheduler_settings(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    require_portal_manage_access(user)
    config = await config_svc.get_scheduler_config(db)
    return ApiResponse(data=_to_response(config))


@router.put("/schedulers", response_model=ApiResponse[SchedulerSettingsResponse])
async def update_scheduler_settings(
    body: SchedulerSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    require_portal_manage_access(user)
    current = await config_svc.get_scheduler_config(db)
    target = replace(
        current,
        **(
            {
                "sign_poll_enabled": body.sign_poll.enabled,
                "sign_poll_cron": body.sign_poll.cron,
            }
            if body.sign_poll is not None
            else {}
        ),
        **(
            {
                "scan_enabled": body.scan.enabled,
                "scan_cron": body.scan.cron,
            }
            if body.scan is not None
            else {}
        ),
        **(
            {
                "boe_pack_enabled": body.boe_pack.enabled,
                "boe_pack_cron": body.boe_pack.cron,
            }
            if body.boe_pack is not None
            else {}
        ),
    )
    await config_svc.update_scheduler_config(db, target)
    await audit_service.write_audit_log(
        db,
        tenant_id=user.current_org_id or config_svc.SCHEDULER_TENANT_ID,
        actor_id=user.user_id,
        action=ACTION_SCHEDULER_SETTINGS_UPDATED,
        resource_type="settings",
        resource_id="schedulers",
        details={
            "sign_poll": {
                "enabled": target.sign_poll_enabled,
                "cron": target.sign_poll_cron,
            },
            "scan": {
                "enabled": target.scan_enabled,
                "cron": target.scan_cron,
            },
            "boe_pack": {
                "enabled": target.boe_pack_enabled,
                "cron": target.boe_pack_cron,
            },
        },
    )
    await db.commit()
    return ApiResponse(data=_to_response(target), message="调度器设置已保存")
