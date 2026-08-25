from fastapi import APIRouter, Depends

from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.integration import IntegrationEndpointsResponse
from app.services.runtime_endpoints import client_integration_endpoints

router = APIRouter()


@router.get(
    "/integration-endpoints",
    response_model=ApiResponse[IntegrationEndpointsResponse],
)
async def get_integration_endpoints(
    user: UserCache = Depends(get_current_user),
):
    require_tenant_access(user)
    payload = client_integration_endpoints()
    return ApiResponse(data=IntegrationEndpointsResponse(sdmsBaseUrl=payload["sdmsBaseUrl"]))
