from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.resource import HumanActionConfirmRequest, HumanActionResponse
from app.services import human_action_service

router = APIRouter()


@router.get("/pending", response_model=ApiResponse[list[HumanActionResponse]])
async def list_pending_human_actions(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    actions = await human_action_service.list_pending_human_actions(db, tenant_id)
    return ApiResponse(data=[HumanActionResponse.model_validate(a) for a in actions])


@router.get("/{action_id}", response_model=ApiResponse[HumanActionResponse])
async def get_human_action(
    action_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    action = await human_action_service.get_human_action(db, tenant_id, action_id)
    return ApiResponse(data=HumanActionResponse.model_validate(action))


@router.post("/{action_id}/open", response_model=ApiResponse[HumanActionResponse])
async def open_human_action(
    action_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    action = await human_action_service.open_human_action(db, tenant_id, action_id, user)
    return ApiResponse(data=HumanActionResponse.model_validate(action))


@router.post("/{action_id}/confirm", response_model=ApiResponse[HumanActionResponse])
async def confirm_human_action(
    action_id: str,
    body: HumanActionConfirmRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    action = await human_action_service.confirm_human_action(
        db,
        tenant_id,
        action_id,
        user,
        resume_running=bool(body.resume_running) if body else False,
    )
    return ApiResponse(data=HumanActionResponse.model_validate(action))


@router.post("/{action_id}/cancel", response_model=ApiResponse[HumanActionResponse])
async def cancel_human_action(
    action_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    action = await human_action_service.cancel_human_action(db, tenant_id, action_id, user)
    return ApiResponse(data=HumanActionResponse.model_validate(action))
