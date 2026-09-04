"""Central API router."""

from fastapi import APIRouter

from app.api import (
    artifacts,
    dashboard,
    human_actions,
    integration,
    mcp,
    portal_accounts,
    portal_categories,
    process_instances,
    rpa_dispatch,
    rpa_runs,
    rpa_workers,
    scheduler_jobs,
    session,
    settings,
    statements,
    tasks,
    timers,
    workflow_bindings,
    workflow_templates,
)

api_router = APIRouter()
worker_api_router = APIRouter(prefix="/worker-api")
mcp_router = APIRouter(prefix="/mcp")


@api_router.get("/health", tags=["系统"])
async def health_check():
    return {"status": "ok"}


api_router.include_router(dashboard.router, tags=["Dashboard"])
api_router.include_router(session.router, tags=["Session"])
api_router.include_router(integration.router, tags=["Integration"])
api_router.include_router(portal_accounts.router, prefix="/portal-accounts", tags=["Portal Account"])
api_router.include_router(portal_categories.router, prefix="/portal-categories", tags=["Portal Category"])
api_router.include_router(workflow_templates.router, prefix="/workflow-templates", tags=["Workflow Template"])
api_router.include_router(workflow_bindings.router, prefix="/workflow-bindings", tags=["Workflow Binding"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Automation Task"])
api_router.include_router(process_instances.router, prefix="/process-instances", tags=["Process Instance"])
api_router.include_router(statements.router, prefix="/statements", tags=["Statement"])
api_router.include_router(rpa_runs.router, prefix="/runs", tags=["RPA Run"])
api_router.include_router(human_actions.router, prefix="/human-actions", tags=["Human Action"])
api_router.include_router(artifacts.router, prefix="/artifacts", tags=["Artifact"])
api_router.include_router(rpa_workers.router, prefix="/rpa-workers", tags=["RPA Worker"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(scheduler_jobs.router, prefix="/scheduler-jobs", tags=["Scheduler Job"])
api_router.include_router(timers.router, prefix="/timers", tags=["Timer"])

worker_api_router.include_router(rpa_dispatch.router, tags=["RPA Worker API"])
mcp_router.include_router(mcp.router, tags=["MCP"])
