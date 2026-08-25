from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.enums import PortalPermission
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardSummary
from app.services import dashboard_service
from app.services.permission_service import list_accessible_portal_ids

router = APIRouter()


@router.get("/dashboard/summary", response_model=ApiResponse[DashboardSummary])
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    accessible_ids = await list_accessible_portal_ids(
        db, user, tenant_id, PortalPermission.PORTAL_VIEW
    )
    summary = await dashboard_service.get_dashboard_summary(
        db, tenant_id, accessible_portal_ids=accessible_ids
    )
    return ApiResponse(data=summary)
