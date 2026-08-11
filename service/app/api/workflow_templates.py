from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.workflow import WorkflowTemplateCreate, WorkflowTemplateResponse, WorkflowTemplateUpdate
from app.services import workflow_template_service

router = APIRouter()


@router.get("", response_model=ApiResponse[list[WorkflowTemplateResponse]])
async def list_workflow_templates(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    templates = await workflow_template_service.list_workflow_templates(db, tenant_id)
    return ApiResponse(data=[WorkflowTemplateResponse.model_validate(t) for t in templates])


@router.post("", response_model=ApiResponse[WorkflowTemplateResponse])
async def create_workflow_template(
    body: WorkflowTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    template = await workflow_template_service.create_workflow_template(db, tenant_id, user, body)
    return ApiResponse(data=WorkflowTemplateResponse.model_validate(template))


@router.get("/{template_id}", response_model=ApiResponse[WorkflowTemplateResponse])
async def get_workflow_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    template = await workflow_template_service.get_workflow_template(db, tenant_id, template_id)
    return ApiResponse(data=WorkflowTemplateResponse.model_validate(template))


@router.patch("/{template_id}", response_model=ApiResponse[WorkflowTemplateResponse])
async def update_workflow_template(
    template_id: str,
    body: WorkflowTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    template = await workflow_template_service.update_workflow_template(db, tenant_id, template_id, body)
    return ApiResponse(data=WorkflowTemplateResponse.model_validate(template))


@router.delete("/{template_id}", response_model=ApiResponse[None])
async def delete_workflow_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await workflow_template_service.delete_workflow_template(
        db,
        tenant_id,
        template_id,
        user,
    )
    return ApiResponse(data=None, message="已删除")


@router.post("/{template_id}/enable", response_model=ApiResponse[WorkflowTemplateResponse])
async def enable_workflow_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    template = await workflow_template_service.enable_workflow_template(db, tenant_id, template_id)
    return ApiResponse(data=WorkflowTemplateResponse.model_validate(template))


@router.post("/{template_id}/disable", response_model=ApiResponse[WorkflowTemplateResponse])
async def disable_workflow_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    template = await workflow_template_service.disable_workflow_template(db, tenant_id, template_id)
    return ApiResponse(data=WorkflowTemplateResponse.model_validate(template))
