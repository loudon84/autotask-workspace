"""Workflow template CRUD."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import WorkflowTemplateStatus
from app.models.user_cache import UserCache
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.models.workflow_template_version import WorkflowTemplateVersion
from app.schemas.workflow import WorkflowTemplateCreate, WorkflowTemplateUpdate
from app.services import audit_service
from app.services.json_utils import dumps_json


async def list_workflow_templates(db: AsyncSession, tenant_id: str) -> list[WorkflowTemplate]:
    result = await db.execute(
        select(WorkflowTemplate)
        .where(
            WorkflowTemplate.tenant_id == tenant_id,
            not_deleted(WorkflowTemplate),
        )
        .order_by(WorkflowTemplate.created_at.desc())
    )
    return list(result.scalars().all())


async def get_workflow_template(db: AsyncSession, tenant_id: str, template_id: str) -> WorkflowTemplate:
    template = (
        await db.execute(
            select(WorkflowTemplate).where(
                WorkflowTemplate.id == template_id,
                WorkflowTemplate.tenant_id == tenant_id,
                not_deleted(WorkflowTemplate),
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise NotFoundError(message="工作流模板不存在", message_key="errors.autotask.workflow_not_found")
    return template


async def create_workflow_template(
    db: AsyncSession,
    tenant_id: str,
    user: UserCache,
    body: WorkflowTemplateCreate,
) -> WorkflowTemplate:
    existing = (
        await db.execute(
            select(WorkflowTemplate).where(
                WorkflowTemplate.tenant_id == tenant_id,
                WorkflowTemplate.code == body.code,
                not_deleted(WorkflowTemplate),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError(message="工作流编码已存在", message_key="errors.autotask.workflow_code_duplicate")

    template = WorkflowTemplate(
        tenant_id=tenant_id,
        name=body.name,
        code=body.code,
        description=body.description,
        entity_type=body.entity_type,
        category=body.category,
        status=body.status,
        version=body.version,
        input_schema=dumps_json(body.input_schema),
        business_steps=dumps_json(body.business_steps),
        created_by=user.user_id,
    )
    db.add(template)
    await db.flush()
    db.add(
        WorkflowTemplateVersion(
            template_id=template.id,
            version=template.version,
            snapshot=dumps_json(body.model_dump()),
            created_by=user.user_id,
        )
    )
    await db.commit()
    await db.refresh(template)
    return template


async def update_workflow_template(
    db: AsyncSession,
    tenant_id: str,
    template_id: str,
    body: WorkflowTemplateUpdate,
) -> WorkflowTemplate:
    template = await get_workflow_template(db, tenant_id, template_id)
    data = body.model_dump(exclude_unset=True, by_alias=False)
    if "input_schema" in data:
        data["input_schema"] = dumps_json(data["input_schema"])
    if "business_steps" in data:
        data["business_steps"] = dumps_json(data["business_steps"])
    for field, value in data.items():
        setattr(template, field, value)
    await db.commit()
    await db.refresh(template)
    return template


async def set_workflow_template_status(
    db: AsyncSession,
    tenant_id: str,
    template_id: str,
    status: str,
) -> WorkflowTemplate:
    template = await get_workflow_template(db, tenant_id, template_id)
    template.status = status
    await db.commit()
    await db.refresh(template)
    return template


async def enable_workflow_template(db: AsyncSession, tenant_id: str, template_id: str) -> WorkflowTemplate:
    return await set_workflow_template_status(db, tenant_id, template_id, WorkflowTemplateStatus.ENABLED)


async def disable_workflow_template(db: AsyncSession, tenant_id: str, template_id: str) -> WorkflowTemplate:
    return await set_workflow_template_status(db, tenant_id, template_id, WorkflowTemplateStatus.DISABLED)


async def delete_workflow_template(
    db: AsyncSession,
    tenant_id: str,
    template_id: str,
    actor: UserCache,
) -> None:
    template = await get_workflow_template(db, tenant_id, template_id)
    if template.status not in {
        WorkflowTemplateStatus.DRAFT.value,
        WorkflowTemplateStatus.DISABLED.value,
    }:
        raise ConflictError(
            message="启用中的模板不能删除，请先禁用",
            message_key="errors.autotask.workflow_delete_requires_disabled",
        )

    binding_id = (
        await db.execute(
            select(WorkflowBinding.id)
            .where(
                WorkflowBinding.workflow_template_id == template.id,
                not_deleted(WorkflowBinding),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if binding_id is not None:
        raise ConflictError(
            message="模板已被 Binding 引用，只能禁用",
            message_key="errors.autotask.workflow_delete_binding_referenced",
        )

    historical_task_id = (
        await db.execute(
            select(AutomationTask.id)
            .join(
                WorkflowBinding,
                AutomationTask.workflow_binding_id == WorkflowBinding.id,
            )
            .where(
                AutomationTask.tenant_id == tenant_id,
                WorkflowBinding.workflow_template_id == template.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if historical_task_id is not None:
        raise ConflictError(
            message="模板已被历史任务引用，只能禁用",
            message_key="errors.autotask.workflow_delete_task_referenced",
        )

    template.soft_delete()
    await audit_service.write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=actor.user_id,
        action=audit_service.ACTION_WORKFLOW_TEMPLATE_DELETED,
        resource_type=audit_service.WORKFLOW_TEMPLATE_RESOURCE_TYPE,
        resource_id=template.id,
        details={"name": template.name, "code": template.code},
    )
    await db.commit()
