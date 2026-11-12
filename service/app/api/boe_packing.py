from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_portal_visible, require_tenant_access
from app.models.base import not_deleted
from app.models.enums import PortalPermission
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache
from app.schemas.boe_packing import (
    BoeAttachmentDeleteResult,
    BoeMatchResponse,
    BoePackingAttachmentStored,
    BoePackingListItem,
    BoePackingPatchRequest,
)
from app.schemas.common import ApiResponse
from app.services import boe_packing_service as svc
from app.services.permission_service import list_accessible_portal_ids

router = APIRouter()


async def _portals_by_id(db: AsyncSession, ids: set[str]) -> dict[str, PortalAccount]:
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(PortalAccount).where(PortalAccount.id.in_(ids), not_deleted(PortalAccount))
        )
    ).scalars().all()
    return {row.id: row for row in rows}


@router.get("", response_model=ApiResponse[list[BoePackingListItem]])
async def list_boe_packing(
    stage: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    accessible_ids = await list_accessible_portal_ids(
        db, user, tenant_id, PortalPermission.PORTAL_VIEW
    )
    instances = await svc.list_instances(
        db,
        tenant_id,
        stage=stage,
        status=status,
        keyword=keyword,
        accessible_portal_ids=accessible_ids,
    )
    portals = await _portals_by_id(db, {item.portal_account_id for item in instances})
    task_status = await svc.latest_task_status_map(db, [item.id for item in instances])
    return ApiResponse(
        data=[
            BoePackingListItem.model_validate(
                svc.to_list_item(
                    item,
                    portals.get(item.portal_account_id),
                    latest_task_status=task_status.get(item.id, ""),
                )
            )
            for item in instances
        ]
    )


@router.post("/match", response_model=ApiResponse[BoeMatchResponse])
async def match_delivery_plans(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    result = await svc.match_delivery_plans(db, tenant_id, actor=user.user_id)
    return ApiResponse(data=BoeMatchResponse.model_validate(result))


@router.get("/{instance_id}")
async def get_boe_packing(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await svc.get_packing_instance(db, tenant_id, instance_id)
    await require_portal_visible(db, user, instance.portal_account_id)
    portals = await _portals_by_id(db, {instance.portal_account_id})
    portal = portals[instance.portal_account_id]
    return ApiResponse(data=await svc.to_detail(db, instance, portal))


@router.patch("/{instance_id}")
async def patch_boe_packing(
    instance_id: str,
    body: BoePackingPatchRequest,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await svc.get_packing_instance(db, tenant_id, instance_id)
    await require_portal_visible(db, user, instance.portal_account_id)
    payload = body.model_dump(by_alias=True, exclude_none=True)
    instance = await svc.patch_instance(db, tenant_id, instance_id, payload, user)
    portals = await _portals_by_id(db, {instance.portal_account_id})
    return ApiResponse(data=await svc.to_detail(db, instance, portals[instance.portal_account_id]))


@router.post("/{instance_id}/retry")
async def retry_boe_packing(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await svc.get_packing_instance(db, tenant_id, instance_id)
    await require_portal_visible(db, user, instance.portal_account_id)
    instance = await svc.retry_instance(db, tenant_id, instance_id, user)
    portals = await _portals_by_id(db, {instance.portal_account_id})
    return ApiResponse(data=await svc.to_detail(db, instance, portals[instance.portal_account_id]))


@router.post("/{instance_id}/cancel")
async def cancel_boe_packing(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await svc.get_packing_instance(db, tenant_id, instance_id)
    await require_portal_visible(db, user, instance.portal_account_id)
    instance = await svc.cancel_instance(db, tenant_id, instance_id, user)
    portals = await _portals_by_id(db, {instance.portal_account_id})
    return ApiResponse(data=await svc.to_detail(db, instance, portals[instance.portal_account_id]))


@router.post(
    "/{instance_id}/attachments",
    response_model=ApiResponse[BoePackingAttachmentStored],
)
async def upload_boe_attachment(
    instance_id: str,
    attachment_id: Annotated[str, Form(alias="attachmentId")],
    file_type: Annotated[str, Form(alias="type")],
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await svc.get_packing_instance(db, tenant_id, instance_id)
    await require_portal_visible(db, user, instance.portal_account_id)
    content = await file.read()
    saved = await svc.upload_attachment_bytes(
        db,
        tenant_id,
        instance_id,
        attachment_id=attachment_id,
        file_type=file_type,
        filename=file.filename or "",
        content=content,
    )
    return ApiResponse(data=BoePackingAttachmentStored.model_validate(saved))


@router.delete(
    "/{instance_id}/attachments",
    response_model=ApiResponse[BoeAttachmentDeleteResult],
)
async def delete_boe_attachment(
    instance_id: str,
    file_path: str = Query(..., alias="filePath"),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await svc.get_packing_instance(db, tenant_id, instance_id)
    await require_portal_visible(db, user, instance.portal_account_id)
    deleted = await svc.remove_attachment_file(
        db, tenant_id, instance_id, file_path=file_path
    )
    return ApiResponse(data=BoeAttachmentDeleteResult(deleted=deleted))


@router.post("/{instance_id}/submit")
async def submit_boe_packing(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    instance = await svc.get_packing_instance(db, tenant_id, instance_id)
    await require_portal_visible(db, user, instance.portal_account_id)
    instance = await svc.submit_instance(db, tenant_id, instance_id, user)
    portals = await _portals_by_id(db, {instance.portal_account_id})
    return ApiResponse(data=await svc.to_detail(db, instance, portals[instance.portal_account_id]))
