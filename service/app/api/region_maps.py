from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse, CamelModel
from app.services import region_code_map_service as svc
from pydantic import Field

router = APIRouter()


class RegionMapResponse(CamelModel):
    id: str
    region_code: str = Field(serialization_alias="regionCode")
    default_name: str = Field(serialization_alias="defaultName")
    boe_name: str | None = Field(None, serialization_alias="boeName")
    updated_by_name: str = Field("", serialization_alias="updatedByName")


class RegionMapUpsert(CamelModel):
    region_code: str = Field(alias="regionCode")
    default_name: str = Field(alias="defaultName")
    boe_name: str | None = Field(None, alias="boeName")


@router.get("", response_model=ApiResponse[list[RegionMapResponse]])
async def list_region_maps(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    rows = await svc.list_maps(db, tenant_id)
    return ApiResponse(data=[RegionMapResponse.model_validate(row) for row in rows])


@router.post("", response_model=ApiResponse[RegionMapResponse])
async def upsert_region_map(
    body: RegionMapUpsert,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    row = await svc.upsert_map(
        db,
        tenant_id,
        region_code=body.region_code,
        default_name=body.default_name,
        boe_name=body.boe_name,
        actor=user,
    )
    return ApiResponse(data=RegionMapResponse.model_validate(row))


@router.delete("/{map_id}", response_model=ApiResponse[None])
async def delete_region_map(
    map_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await svc.delete_map(db, tenant_id, map_id)
    return ApiResponse(data=None, message="已删除")
