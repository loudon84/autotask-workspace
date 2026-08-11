"""Automation task CRUD and lifecycle."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, TaskNotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import BindingStatus, TaskStatus
from app.models.rpa_run import RpaRun
from app.models.task_message import TaskMessage
from app.models.user_cache import UserCache
from app.schemas.task import AutomationTaskCreate, AutomationTaskUpdate
from app.services.json_utils import dumps_json, loads_json
from app.services.portal_account_service import get_portal_account
from app.services.task_state_machine import transition
from app.services.task_successor_service import (
    TARGET_WORKFLOW_CODE,
    validate_delivery_confirmation_input,
)
from app.services.workflow_binding_service import get_workflow_binding
from app.services.workflow_template_service import get_workflow_template


async def list_tasks(db: AsyncSession, tenant_id: str, status: str | None = None) -> list[AutomationTask]:
    query = select(AutomationTask).where(
        AutomationTask.tenant_id == tenant_id,
        not_deleted(AutomationTask),
    )
    if status:
        query = query.where(AutomationTask.status == status)
    result = await db.execute(query.order_by(AutomationTask.created_at.desc()))
    return list(result.scalars().all())


async def get_task(db: AsyncSession, tenant_id: str, task_id: str) -> AutomationTask:
    task = (
        await db.execute(
            select(AutomationTask).where(
                AutomationTask.id == task_id,
                AutomationTask.tenant_id == tenant_id,
                not_deleted(AutomationTask),
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise TaskNotFoundError()
    return task


async def create_task(
    db: AsyncSession,
    tenant_id: str,
    user: UserCache,
    body: AutomationTaskCreate,
) -> AutomationTask:
    await get_portal_account(db, tenant_id, body.portal_account_id)
    binding = await get_workflow_binding(db, tenant_id, body.workflow_binding_id)
    if binding.status != BindingStatus.ENABLED:
        raise BadRequestError(message="工作流绑定未启用", message_key="errors.autotask.binding_disabled")

    task = AutomationTask(
        tenant_id=tenant_id,
        title=body.title,
        task_type=body.task_type,
        portal_account_id=body.portal_account_id,
        workflow_binding_id=body.workflow_binding_id,
        entity_type=body.entity_type,
        erp_entity_code=body.erp_entity_code,
        erp_entity_name=body.erp_entity_name,
        status=TaskStatus.DRAFT,
        priority=body.priority,
        input=dumps_json(body.input),
        created_by=user.user_id,
        assigned_to=body.assigned_to,
    )
    db.add(task)
    await db.flush()
    db.add(
        TaskMessage(
            task_id=task.id,
            role="system",
            content=f"任务已创建: {task.title}",
            created_by=user.user_id,
        )
    )
    await db.commit()
    await db.refresh(task)
    return task


async def update_task(
    db: AsyncSession,
    tenant_id: str,
    task_id: str,
    body: AutomationTaskUpdate,
) -> AutomationTask:
    task = await get_task(db, tenant_id, task_id)
    data = body.model_dump(exclude_unset=True, by_alias=False)
    if "input" in data:
        if task.status not in {TaskStatus.DRAFT, TaskStatus.READY}:
            raise BadRequestError(
                message="任务进入队列后不允许修改输入参数",
                message_key="errors.autotask.task_input_immutable",
            )
        data["input"] = dumps_json(data["input"])
    for field, value in data.items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


async def submit_task(db: AsyncSession, tenant_id: str, task_id: str) -> AutomationTask:
    task = await get_task(db, tenant_id, task_id)
    transition(task, TaskStatus.READY)
    await db.commit()
    await db.refresh(task)
    return task


async def start_task(db: AsyncSession, tenant_id: str, task_id: str) -> AutomationTask:
    task = await get_task(db, tenant_id, task_id)
    binding = await get_workflow_binding(db, tenant_id, task.workflow_binding_id)
    await _validate_execution_input(db, tenant_id, task, binding.workflow_template_id)
    if task.status == TaskStatus.DRAFT:
        transition(task, TaskStatus.READY)
    transition(task, TaskStatus.QUEUED)
    run = RpaRun(
        task_id=task.id,
        rpa_flow_id=binding.rpa_flow_id,
        status=TaskStatus.QUEUED,
    )
    db.add(run)
    await db.commit()
    await db.refresh(task)
    return task


async def cancel_task(db: AsyncSession, tenant_id: str, task_id: str) -> AutomationTask:
    task = await get_task(db, tenant_id, task_id)
    transition(task, TaskStatus.CANCELLED)
    runs = (
        await db.execute(
            select(RpaRun).where(RpaRun.task_id == task.id, not_deleted(RpaRun))
        )
    ).scalars().all()
    for run in runs:
        if run.status not in {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            run.status = TaskStatus.CANCELLED
            run.ended_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(task)
    return task


async def retry_task(db: AsyncSession, tenant_id: str, task_id: str) -> AutomationTask:
    task = await get_task(db, tenant_id, task_id)
    if task.status != TaskStatus.FAILED:
        raise BadRequestError(message="仅失败任务可重试", message_key="errors.autotask.retry_not_allowed")
    binding = await get_workflow_binding(db, tenant_id, task.workflow_binding_id)
    await _validate_execution_input(db, tenant_id, task, binding.workflow_template_id)
    transition(task, TaskStatus.READY)
    transition(task, TaskStatus.QUEUED)
    db.add(RpaRun(task_id=task.id, rpa_flow_id=binding.rpa_flow_id, status=TaskStatus.QUEUED))
    await db.commit()
    await db.refresh(task)
    return task


async def mark_success_manual(db: AsyncSession, tenant_id: str, task_id: str, user: UserCache) -> AutomationTask:
    task = await get_task(db, tenant_id, task_id)
    if task.status not in {TaskStatus.WAITING_HUMAN, TaskStatus.HUMAN_OPERATING, TaskStatus.RUNNING}:
        raise BadRequestError(message="当前状态不允许人工确认完成", message_key="errors.autotask.manual_success_not_allowed")
    transition(task, TaskStatus.SUCCESS_MANUAL)
    task.progress = 100
    db.add(
        TaskMessage(
            task_id=task.id,
            role="system",
            content=f"用户 {user.name} 已人工确认任务完成",
            created_by=user.user_id,
        )
    )
    await db.commit()
    await db.refresh(task)
    return task


async def list_task_messages(db: AsyncSession, tenant_id: str, task_id: str) -> list[TaskMessage]:
    await get_task(db, tenant_id, task_id)
    result = await db.execute(
        select(TaskMessage).where(
            TaskMessage.task_id == task_id,
            not_deleted(TaskMessage),
        ).order_by(TaskMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def list_task_runs(db: AsyncSession, tenant_id: str, task_id: str) -> list[RpaRun]:
    await get_task(db, tenant_id, task_id)
    result = await db.execute(
        select(RpaRun).where(RpaRun.task_id == task_id, not_deleted(RpaRun)).order_by(RpaRun.created_at.desc())
    )
    return list(result.scalars().all())


def task_input_dict(task: AutomationTask) -> dict:
    return loads_json(task.input, {})


async def _validate_execution_input(
    db: AsyncSession,
    tenant_id: str,
    task: AutomationTask,
    workflow_template_id: str,
) -> None:
    template = await get_workflow_template(db, tenant_id, workflow_template_id)
    if template.code == TARGET_WORKFLOW_CODE:
        validate_delivery_confirmation_input(task_input_dict(task))
