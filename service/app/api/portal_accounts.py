from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import (
    get_current_user,
    require_permission,
    require_portal_manage_access,
    require_tenant_access,
)
from app.models.enums import PortalPermission
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.portal_account import (
    PortalAccessGrantCreate,
    PortalAccessGrantResponse,
    PortalAccountCreate,
    PortalAccountResponse,
    PortalAccountUpdate,
    PortalListPageResponse,
    PortalTestOpenResponse,
)
from app.services import portal_account_service

router = APIRouter()


@router.get("", response_model=ApiResponse[PortalListPageResponse])
async def list_portal_accounts(
    entity_type: str | None = Query(None, alias="entityType"),
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    result = await portal_account_service.list_portal_accounts(
        db,
        tenant_id,
        user,
        entity_type=entity_type,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(data=result)


@router.post("", response_model=ApiResponse[PortalAccountResponse])
async def create_portal_account(
    body: PortalAccountCreate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    # require_portal_manage_access(user)
    tenant_id = require_tenant_access(user)
    account = await portal_account_service.create_portal_account(db, tenant_id, user, body)
    return ApiResponse(data=PortalAccountResponse.model_validate(account))


@router.get("/{account_id}", response_model=ApiResponse[PortalAccountResponse])
async def get_portal_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await require_permission(db, user, account_id, PortalPermission.PORTAL_VIEW)
    account = await portal_account_service.get_portal_account(db, tenant_id, account_id)
    return ApiResponse(data=PortalAccountResponse.model_validate(account))


@router.patch("/{account_id}", response_model=ApiResponse[PortalAccountResponse])
async def update_portal_account(
    account_id: str,
    body: PortalAccountUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await require_permission(db, user, account_id, PortalPermission.PORTAL_EDIT)
    account = await portal_account_service.update_portal_account(db, tenant_id, account_id, body, user)
    return ApiResponse(data=PortalAccountResponse.model_validate(account))


@router.delete("/{account_id}", response_model=ApiResponse[None])
async def delete_portal_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await require_permission(db, user, account_id, PortalPermission.PORTAL_EDIT)
    await portal_account_service.delete_portal_account(db, tenant_id, account_id, user)
    return ApiResponse(data=None, message="已删除")


@router.post("/{account_id}/test-open", response_model=ApiResponse[PortalTestOpenResponse])
async def test_open_portal_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await require_permission(db, user, account_id, PortalPermission.PORTAL_OPEN_WEB)
    result = await portal_account_service.test_open_portal_account(db, tenant_id, account_id, user)
    return ApiResponse(data=result)


@router.get("/{account_id}/access-grants", response_model=ApiResponse[list[PortalAccessGrantResponse]])
async def list_access_grants(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await require_permission(db, user, account_id, PortalPermission.PORTAL_MANAGE_PERMISSION)
    grants = await portal_account_service.list_access_grants(db, tenant_id, account_id)
    return ApiResponse(data=[PortalAccessGrantResponse.model_validate(g) for g in grants])


@router.post("/{account_id}/access-grants", response_model=ApiResponse[PortalAccessGrantResponse])
async def create_access_grant(
    account_id: str,
    body: PortalAccessGrantCreate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await require_permission(db, user, account_id, PortalPermission.PORTAL_MANAGE_PERMISSION)
    grant = await portal_account_service.create_access_grant(db, tenant_id, account_id, user, body)
    return ApiResponse(data=PortalAccessGrantResponse.model_validate(grant))
