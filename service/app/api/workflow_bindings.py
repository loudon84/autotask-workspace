from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.workflow import WorkflowBindingCreate, WorkflowBindingResponse, WorkflowBindingUpdate
from app.services import workflow_binding_service

router = APIRouter()


@router.get("", response_model=ApiResponse[list[WorkflowBindingResponse]])
async def list_workflow_bindings(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    bindings = await workflow_binding_service.list_workflow_bindings(db, tenant_id)
    return ApiResponse(data=[WorkflowBindingResponse.model_validate(b) for b in bindings])


@router.post("", response_model=ApiResponse[WorkflowBindingResponse])
async def create_workflow_binding(
    body: WorkflowBindingCreate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    binding = await workflow_binding_service.create_workflow_binding(db, tenant_id, user, body)
    return ApiResponse(data=WorkflowBindingResponse.model_validate(binding))


@router.get("/{binding_id}", response_model=ApiResponse[WorkflowBindingResponse])
async def get_workflow_binding(
    binding_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    binding = await workflow_binding_service.get_workflow_binding(db, tenant_id, binding_id)
    return ApiResponse(data=WorkflowBindingResponse.model_validate(binding))


@router.patch("/{binding_id}", response_model=ApiResponse[WorkflowBindingResponse])
async def update_workflow_binding(
    binding_id: str,
    body: WorkflowBindingUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    binding = await workflow_binding_service.update_workflow_binding(db, tenant_id, binding_id, body, user)
    return ApiResponse(data=WorkflowBindingResponse.model_validate(binding))


@router.post("/{binding_id}/enable", response_model=ApiResponse[WorkflowBindingResponse])
async def enable_workflow_binding(
    binding_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    binding = await workflow_binding_service.enable_workflow_binding(db, tenant_id, binding_id)
    return ApiResponse(data=WorkflowBindingResponse.model_validate(binding))


@router.post("/{binding_id}/disable", response_model=ApiResponse[WorkflowBindingResponse])
async def disable_workflow_binding(
    binding_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    binding = await workflow_binding_service.disable_workflow_binding(db, tenant_id, binding_id)
    return ApiResponse(data=WorkflowBindingResponse.model_validate(binding))
