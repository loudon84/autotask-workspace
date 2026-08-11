"""Map automation tasks to frontend AutoTask contract."""

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import TaskStatus
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.schemas.task import TaskListItemResponse, TaskListPageResponse
from app.services.json_utils import loads_json

_STATUS_STEP_LABELS: dict[str, str] = {
    TaskStatus.DRAFT: "草稿",
    TaskStatus.READY: "等待执行",
    TaskStatus.QUEUED: "排队中",
    TaskStatus.LEASED: "已分配",
    TaskStatus.RUNNING: "执行中",
    TaskStatus.WAITING_HUMAN: "等待人工",
    TaskStatus.HUMAN_OPERATING: "人工操作中",
    TaskStatus.SUCCESS: "已完成",
    TaskStatus.SUCCESS_MANUAL: "人工确认完成",
    TaskStatus.PARTIAL_SUCCESS: "部分成功",
    TaskStatus.FAILED: "失败",
    TaskStatus.CANCELLED: "已取消",
}


def _format_priority(priority: str) -> str:
    return priority.lower() if priority else "normal"


def _format_current_step(task: AutomationTask) -> str | None:
    if task.current_step:
        return task.current_step
    return _STATUS_STEP_LABELS.get(task.status)


def _format_datetime(value: datetime) -> datetime:
    return value


async def _load_related_maps(
    db: AsyncSession,
    tenant_id: str,
    tasks: list[AutomationTask],
) -> tuple[dict[str, PortalAccount], dict[str, WorkflowBinding], dict[str, WorkflowTemplate], dict[str, UserCache]]:
    portal_ids = {t.portal_account_id for t in tasks}
    binding_ids = {t.workflow_binding_id for t in tasks}
    user_ids: set[str] = set()
    for task in tasks:
        user_ids.add(task.created_by)
        if task.assigned_to:
            user_ids.add(task.assigned_to)

    portals: dict[str, PortalAccount] = {}
    if portal_ids:
        rows = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.tenant_id == tenant_id,
                    PortalAccount.id.in_(portal_ids),
                    not_deleted(PortalAccount),
                )
            )
        ).scalars().all()
        portals = {row.id: row for row in rows}

    bindings: dict[str, WorkflowBinding] = {}
    template_ids: set[str] = set()
    if binding_ids:
        rows = (
            await db.execute(
                select(WorkflowBinding).where(
                    WorkflowBinding.id.in_(binding_ids),
                    not_deleted(WorkflowBinding),
                )
            )
        ).scalars().all()
        bindings = {row.id: row for row in rows}
        template_ids = {row.workflow_template_id for row in rows}

    templates: dict[str, WorkflowTemplate] = {}
    if template_ids:
        rows = (
            await db.execute(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.tenant_id == tenant_id,
                    WorkflowTemplate.id.in_(template_ids),
                    not_deleted(WorkflowTemplate),
                )
            )
        ).scalars().all()
        templates = {row.id: row for row in rows}

    users: dict[str, UserCache] = {}
    if user_ids:
        rows = (
            await db.execute(
                select(UserCache).where(UserCache.user_id.in_(user_ids), not_deleted(UserCache))
            )
        ).scalars().all()
        users = {row.user_id: row for row in rows}

    return portals, bindings, templates, users


def _resolve_owner(task: AutomationTask, users: dict[str, UserCache]) -> str:
    owner_id = task.assigned_to or task.created_by
    user = users.get(owner_id)
    if user and user.name:
        return user.name
    return owner_id


def build_task_list_item(
    task: AutomationTask,
    *,
    portals: dict[str, PortalAccount],
    bindings: dict[str, WorkflowBinding],
    templates: dict[str, WorkflowTemplate],
    users: dict[str, UserCache],
) -> TaskListItemResponse:
    portal = portals.get(task.portal_account_id)
    binding = bindings.get(task.workflow_binding_id)
    template = templates.get(binding.workflow_template_id) if binding else None

    return TaskListItemResponse(
        id=task.id,
        title=task.title,
        task_type=task.task_type,
        customer_name=task.erp_entity_name,
        portal_id=task.portal_account_id,
        srm_portal_name=portal.portal_name if portal else "",
        workflow_template_id=binding.workflow_template_id if binding else "",
        workflow_template_name=template.name if template else "",
        status=task.status,
        priority=_format_priority(task.priority),
        owner=_resolve_owner(task, users),
        input=loads_json(task.input, {}),
        current_step=_format_current_step(task),
        progress=task.progress,
        source_task_id=getattr(task, "source_task_id", None),
        source_run_id=getattr(task, "source_run_id", None),
        created_at=_format_datetime(task.created_at),
        updated_at=_format_datetime(task.updated_at),
    )


async def build_task_list_items(
    db: AsyncSession,
    tenant_id: str,
    tasks: list[AutomationTask],
) -> list[TaskListItemResponse]:
    if not tasks:
        return []
    portals, bindings, templates, users = await _load_related_maps(db, tenant_id, tasks)
    return [
        build_task_list_item(
            task,
            portals=portals,
            bindings=bindings,
            templates=templates,
            users=users,
        )
        for task in tasks
    ]


async def build_task_list_item_for_task(
    db: AsyncSession,
    tenant_id: str,
    task: AutomationTask,
) -> TaskListItemResponse:
    items = await build_task_list_items(db, tenant_id, [task])
    return items[0]


async def list_tasks_for_frontend(
    db: AsyncSession,
    tenant_id: str,
    *,
    status: str | None = None,
    customer_name: str | None = None,
    task_type: str | None = None,
    workflow_template_id: str | None = None,
    priority: str | None = None,
    owner: str | None = None,
    keyword: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[TaskListItemResponse] | TaskListPageResponse:
    query = select(AutomationTask).where(
        AutomationTask.tenant_id == tenant_id,
        not_deleted(AutomationTask),
    )
    if status:
        query = query.where(AutomationTask.status == status.upper())
    if customer_name:
        query = query.where(AutomationTask.erp_entity_name.ilike(f"%{customer_name}%"))
    if task_type:
        query = query.where(AutomationTask.task_type == task_type)
    if priority:
        query = query.where(AutomationTask.priority == priority.upper())
    if keyword:
        query = query.where(
            or_(
                AutomationTask.title.ilike(f"%{keyword}%"),
                AutomationTask.erp_entity_name.ilike(f"%{keyword}%"),
                AutomationTask.task_type.ilike(f"%{keyword}%"),
            )
        )
    if workflow_template_id:
        binding_ids = (
            await db.execute(
                select(WorkflowBinding.id).where(
                    WorkflowBinding.workflow_template_id == workflow_template_id,
                    not_deleted(WorkflowBinding),
                )
            )
        ).scalars().all()
        if not binding_ids:
            if page is not None or page_size is not None:
                return TaskListPageResponse(items=[], total=0, page=page or 1, page_size=page_size or 20)
            return []
        query = query.where(AutomationTask.workflow_binding_id.in_(binding_ids))

    query = query.order_by(AutomationTask.created_at.desc())
    tasks = list((await db.execute(query)).scalars().all())

    if owner:
        portals, bindings, templates, users = await _load_related_maps(db, tenant_id, tasks)
        tasks = [task for task in tasks if _resolve_owner(task, users) == owner or (task.assigned_to or task.created_by) == owner]

    if page is not None or page_size is not None:
        current_page = page or 1
        size = page_size or 20
        total = len(tasks)
        start = (current_page - 1) * size
        page_tasks = tasks[start : start + size]
        items = await build_task_list_items(db, tenant_id, page_tasks)
        return TaskListPageResponse(items=items, total=total, page=current_page, page_size=size)

    return await build_task_list_items(db, tenant_id, tasks)
