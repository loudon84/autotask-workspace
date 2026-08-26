"""Login/refresh forces Task to copy current Auth flags into user cache."""

from fastapi import APIRouter, Depends

from app.core.security import get_fresh_current_user
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.session import SessionUser

router = APIRouter()


@router.post("/session/sync", response_model=ApiResponse[SessionUser])
async def sync_session(user: UserCache = Depends(get_fresh_current_user)):
    return ApiResponse(
        data=SessionUser(
            id=user.user_id,
            name=user.name,
            email=user.email,
            current_org_id=user.current_org_id,
            portal_org_role=user.portal_org_role,
            is_super_admin=user.is_super_admin,
            is_task_admin=bool(getattr(user, "is_task_admin", False)),
        )
    )
