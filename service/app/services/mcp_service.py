"""MCP tool implementations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_tenant_access
from app.models.enums import PortalPermission
from app.models.user_cache import UserCache
from app.schemas.mcp import McpToolCallRequest, McpToolDefinition
from app.schemas.task import AutomationTaskCreate
from app.services import (
    artifact_service,
    automation_task_service,
    human_action_service,
    portal_account_service,
    workflow_template_service,
)
from app.services.permission_service import check_portal_permission

MCP_TOOLS: list[McpToolDefinition] = [
    McpToolDefinition(
        name="autotask.portal.search",
        description="搜索 Portal 账号",
        input_schema={"type": "object", "properties": {"keyword": {"type": "string"}}},
    ),
    McpToolDefinition(
        name="autotask.portal.get",
        description="获取 Portal 账号详情",
        input_schema={"type": "object", "properties": {"portalAccountId": {"type": "string"}}, "required": ["portalAccountId"]},
    ),
    McpToolDefinition(
        name="autotask.workflow.list",
        description="列出工作流模板",
        input_schema={"type": "object", "properties": {}},
    ),
    McpToolDefinition(
        name="autotask.task.create",
        description="创建自动化任务",
        input_schema={"type": "object"},
    ),
    McpToolDefinition(
        name="autotask.task.get",
        description="获取任务详情",
        input_schema={"type": "object", "properties": {"taskId": {"type": "string"}}, "required": ["taskId"]},
    ),
    McpToolDefinition(
        name="autotask.task.get_status",
        description="获取任务状态",
        input_schema={"type": "object", "properties": {"taskId": {"type": "string"}}, "required": ["taskId"]},
    ),
    McpToolDefinition(
        name="autotask.task.list_messages",
        description="列出任务消息",
        input_schema={"type": "object", "properties": {"taskId": {"type": "string"}}, "required": ["taskId"]},
    ),
    McpToolDefinition(
        name="autotask.human_action.list_pending",
        description="列出待人工操作",
        input_schema={"type": "object", "properties": {}},
    ),
    McpToolDefinition(
        name="autotask.human_action.confirm",
        description="确认人工操作",
        input_schema={
            "type": "object",
            "properties": {
                "humanActionId": {"type": "string"},
                "resumeRunning": {"type": "boolean"},
            },
            "required": ["humanActionId"],
        },
    ),
    McpToolDefinition(
        name="autotask.artifact.list",
        description="列出任务产物",
        input_schema={
            "type": "object",
            "properties": {"taskId": {"type": "string"}, "runId": {"type": "string"}},
            "required": ["taskId"],
        },
    ),
]


async def list_tools() -> list[McpToolDefinition]:
    return MCP_TOOLS


async def call_tool(db: AsyncSession, user: UserCache, request: McpToolCallRequest) -> dict:
    tenant_id = require_tenant_access(user)
    args = request.arguments

    if request.name == "autotask.portal.search":
        keyword = args.get("keyword")
        page = await portal_account_service.list_portal_accounts(
            db,
            tenant_id,
            user,
            keyword=keyword,
            page=1,
            page_size=100,
        )
        return {
            "items": [
                {
                    "id": item.id,
                    "portalName": item.portal_name,
                    "loginAccount": item.login_account,
                }
                for item in page.items
            ]
        }

    if request.name == "autotask.portal.get":
        portal_id = args["portalAccountId"]
        allowed = await check_portal_permission(db, user, tenant_id, portal_id, PortalPermission.PORTAL_VIEW)
        if not allowed:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError(message="无权限查看 Portal", message_key="errors.autotask.permission_denied")
        account = await portal_account_service.get_portal_account(db, tenant_id, portal_id)
        return {
            "id": account.id,
            "portalName": account.portal_name,
            "portalUrl": account.portal_url,
            "loginAccount": account.login_account,
            "status": account.status,
        }

    if request.name == "autotask.workflow.list":
        templates = await workflow_template_service.list_workflow_templates(db, tenant_id)
        return {"items": [{"id": t.id, "name": t.name, "code": t.code, "status": t.status} for t in templates]}

    if request.name == "autotask.task.create":
        body = AutomationTaskCreate.model_validate(args)
        allowed = await check_portal_permission(
            db, user, tenant_id, body.portal_account_id, PortalPermission.PORTAL_VIEW_TASKS
        )
        if not allowed:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError(message="无权限创建任务", message_key="errors.autotask.permission_denied")
        task = await automation_task_service.create_task(db, tenant_id, user, body)
        return {"taskId": task.id, "status": task.status}

    if request.name == "autotask.task.get":
        task = await automation_task_service.get_task(db, tenant_id, args["taskId"])
        return {"id": task.id, "title": task.title, "status": task.status, "progress": task.progress}

    if request.name == "autotask.task.get_status":
        task = await automation_task_service.get_task(db, tenant_id, args["taskId"])
        return {"taskId": task.id, "status": task.status, "progress": task.progress}

    if request.name == "autotask.task.list_messages":
        messages = await automation_task_service.list_task_messages(db, tenant_id, args["taskId"])
        return {"items": [{"id": m.id, "role": m.role, "content": m.content} for m in messages]}

    if request.name == "autotask.human_action.list_pending":
        actions = await human_action_service.list_pending_human_actions(db, tenant_id)
        return {"items": [{"id": a.id, "title": a.title, "status": a.status} for a in actions]}

    if request.name == "autotask.human_action.confirm":
        action = await human_action_service.confirm_human_action(
            db,
            tenant_id,
            args["humanActionId"],
            user,
            resume_running=bool(args.get("resumeRunning", False)),
        )
        return {"humanActionId": action.id, "status": action.status}

    if request.name == "autotask.artifact.list":
        artifacts = await artifact_service.list_artifacts(db, tenant_id, task_id=args["taskId"], run_id=args.get("runId"))
        return {
            "items": [
                {"id": a.id, "name": a.name, "type": a.type, "storageKey": a.storage_key}
                for a in artifacts
            ]
        }

    from app.core.exceptions import BadRequestError
    raise BadRequestError(message=f"未知 MCP 工具: {request.name}", message_key="errors.autotask.mcp_tool_not_found")
