"""Workflow binding CRUD."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.enums import BindingStatus
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache
from app.models.workflow_binding import WorkflowBinding
from app.schemas.workflow import WorkflowBindingCreate, WorkflowBindingUpdate
from app.services import rpa_engine_client
from app.services.json_utils import dumps_json, loads_json
from app.services.portal_account_service import get_portal_account
from app.services.task_successor_service import validate_successor_binding_config
from app.services.workflow_template_service import get_workflow_template


async def list_workflow_bindings(db: AsyncSession, tenant_id: str) -> list[WorkflowBinding]:
    result = await db.execute(
        select(WorkflowBinding)
        .join(PortalAccount, WorkflowBinding.portal_account_id == PortalAccount.id)
        .where(
            PortalAccount.tenant_id == tenant_id,
            not_deleted(WorkflowBinding),
            not_deleted(PortalAccount),
        )
        .order_by(WorkflowBinding.created_at.desc())
    )
    return list(result.scalars().all())


async def get_workflow_binding(db: AsyncSession, tenant_id: str, binding_id: str) -> WorkflowBinding:
    binding = (
        await db.execute(
            select(WorkflowBinding)
            .join(PortalAccount, WorkflowBinding.portal_account_id == PortalAccount.id)
            .where(
                WorkflowBinding.id == binding_id,
                PortalAccount.tenant_id == tenant_id,
                not_deleted(WorkflowBinding),
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if binding is None:
        raise NotFoundError(message="工作流绑定不存在", message_key="errors.autotask.binding_not_found")
    return binding


async def _apply_engine_validation(
    db: AsyncSession,
    *,
    tenant_id: str,
    user: UserCache,
    portal_account_id: str,
    workflow_template_id: str,
    rpa_flow_id: str,
    rpa_flow_version: str,
) -> tuple[str, str]:
    await get_portal_account(db, tenant_id, portal_account_id)
    template = await get_workflow_template(db, tenant_id, workflow_template_id)
    result = await rpa_engine_client.validate_binding(
        rpa_flow_id=rpa_flow_id,
        rpa_flow_version=rpa_flow_version,
        workflow_code=template.code,
        actor_id=user.user_id,
        tenant_id=tenant_id,
    )
    return result["rpaFlowVersionId"], result["checksum"]


async def create_workflow_binding(
    db: AsyncSession,
    tenant_id: str,
    user: UserCache,
    body: WorkflowBindingCreate,
) -> WorkflowBinding:
    version_id, checksum = await _apply_engine_validation(
        db,
        tenant_id=tenant_id,
        user=user,
        portal_account_id=body.portal_account_id,
        workflow_template_id=body.workflow_template_id,
        rpa_flow_id=body.rpa_flow_id,
        rpa_flow_version=body.rpa_flow_version,
    )
    await validate_successor_binding_config(
        db,
        tenant_id=tenant_id,
        source_portal_account_id=body.portal_account_id,
        config=body.config,
    )
    binding = WorkflowBinding(
        portal_account_id=body.portal_account_id,
        workflow_template_id=body.workflow_template_id,
        workflow_template_version=body.workflow_template_version,
        rpa_engine_type=body.rpa_engine_type,
        rpa_flow_id=body.rpa_flow_id,
        rpa_flow_version=body.rpa_flow_version,
        rpa_flow_version_id=version_id,
        flow_checksum_snapshot=checksum,
        status=body.status,
        config=dumps_json(body.config),
        created_by=user.user_id,
    )
    db.add(binding)
    await db.commit()
    await db.refresh(binding)
    return binding


async def update_workflow_binding(
    db: AsyncSession,
    tenant_id: str,
    binding_id: str,
    body: WorkflowBindingUpdate,
    user: UserCache,
) -> WorkflowBinding:
    binding = await get_workflow_binding(db, tenant_id, binding_id)
    data = body.model_dump(exclude_unset=True, by_alias=False)
    final_config = data.get("config", loads_json(binding.config, {}))
    await validate_successor_binding_config(
        db,
        tenant_id=tenant_id,
        source_portal_account_id=binding.portal_account_id,
        source_binding_id=binding.id,
        config=final_config,
    )
    if "config" in data:
        data["config"] = dumps_json(data["config"])

    flow_id = data.get("rpa_flow_id", binding.rpa_flow_id)
    flow_version = data.get("rpa_flow_version", binding.rpa_flow_version)
    needs_validate = "rpa_flow_id" in data or "rpa_flow_version" in data
    if needs_validate:
        version_id, checksum = await _apply_engine_validation(
            db,
            tenant_id=tenant_id,
            user=user,
            portal_account_id=binding.portal_account_id,
            workflow_template_id=binding.workflow_template_id,
            rpa_flow_id=flow_id,
            rpa_flow_version=flow_version,
        )
        data["rpa_flow_version_id"] = version_id
        data["flow_checksum_snapshot"] = checksum

    for field, value in data.items():
        setattr(binding, field, value)
    await db.commit()
    await db.refresh(binding)
    return binding


async def enable_workflow_binding(db: AsyncSession, tenant_id: str, binding_id: str) -> WorkflowBinding:
    binding = await get_workflow_binding(db, tenant_id, binding_id)
    await validate_successor_binding_config(
        db,
        tenant_id=tenant_id,
        source_portal_account_id=binding.portal_account_id,
        source_binding_id=binding.id,
        config=loads_json(binding.config, {}),
    )
    binding.status = BindingStatus.ENABLED
    await db.commit()
    await db.refresh(binding)
    return binding


async def disable_workflow_binding(db: AsyncSession, tenant_id: str, binding_id: str) -> WorkflowBinding:
    binding = await get_workflow_binding(db, tenant_id, binding_id)
    binding.status = BindingStatus.DISABLED
    await db.commit()
    await db.refresh(binding)
    return binding
