import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")

from datetime import UTC, datetime

from app.core.access_log import _infer_response_shape
from app.models.enums import TaskStatus
from app.schemas.dashboard import DashboardStats, DashboardSummary, TaskTypeDistributionItem
from app.services.task_view_service import build_task_list_item


def test_dashboard_summary_nested_shape():
    summary = DashboardSummary(
        stats=DashboardStats(
            pending=2,
            running=1,
            waiting_human=0,
            failed=0,
            completed_today=3,
            success_rate=60.0,
            online_workers=1,
        ),
        task_type_distribution=[TaskTypeDistributionItem(task_type="fetch_po", count=2)],
    )
    payload = summary.model_dump(by_alias=True)
    assert "stats" in payload
    assert payload["stats"]["pending"] == 2
    assert payload["stats"]["waitingHuman"] == 0
    assert payload["stats"]["completedToday"] == 3
    assert payload["taskTypeDistribution"] == [{"taskType": "fetch_po", "count": 2}]


def test_tasks_list_response_is_array_not_dashboard_stats():
    tasks_payload = {"code": 0, "message": "success", "data": []}
    shape, count = _infer_response_shape(tasks_payload)
    assert shape == "list"
    assert count == 0

    dashboard_payload = {
        "code": 0,
        "message": "success",
        "data": {
            "stats": {
                "pending": 0,
                "running": 0,
                "waitingHuman": 0,
                "failed": 0,
                "completedToday": 0,
                "successRate": 0.0,
                "onlineWorkers": 0,
            },
            "taskTypeDistribution": [],
        },
    }
    shape, _ = _infer_response_shape(dashboard_payload)
    assert shape == "dashboard_summary"

    legacy_dashboard_payload = {
        "code": 0,
        "message": "success",
        "data": {"todayTotal": 0, "ready": 0, "running": 0},
    }
    shape, _ = _infer_response_shape(legacy_dashboard_payload)
    assert shape == "dashboard_summary_legacy"


def test_task_list_item_frontend_fields():
    class Portal:
        portal_name = "客户A SRM生产环境"

    class Template:
        name = "SRM 获取采购订单"

    class Binding:
        workflow_template_id = "wf_srm_fetch_po"

    class User:
        name = "张三"

    class Task:
        id = "task_001"
        title = "获取客户A采购订单"
        task_type = "srm_fetch_po"
        portal_account_id = "portal_001"
        workflow_binding_id = "binding_001"
        erp_entity_name = "客户A"
        status = TaskStatus.READY
        priority = "NORMAL"
        input = '{"po_no": "PO-20260629-001"}'
        current_step = None
        progress = 0
        created_by = "user-001"
        assigned_to = "user-001"
        created_at = datetime(2026, 7, 8, 10, 0, 0, tzinfo=UTC)
        updated_at = datetime(2026, 7, 8, 10, 0, 0, tzinfo=UTC)

    item = build_task_list_item(
        Task(),
        portals={"portal_001": Portal()},
        bindings={"binding_001": Binding()},
        templates={"wf_srm_fetch_po": Template()},
        users={"user-001": User()},
    )
    payload = item.model_dump(by_alias=True)
    assert payload["customerName"] == "客户A"
    assert payload["portalId"] == "portal_001"
    assert payload["srmPortalName"] == "客户A SRM生产环境"
    assert payload["workflowTemplateId"] == "wf_srm_fetch_po"
    assert payload["workflowTemplateName"] == "SRM 获取采购订单"
    assert payload["priority"] == "normal"
    assert payload["owner"] == "张三"
    assert payload["currentStep"] == "等待执行"


def test_dashboard_service_success_rate_percentage():
    class Task:
        def __init__(self, status: str, task_type: str):
            self.status = status
            self.task_type = task_type

    tasks = [
        Task(TaskStatus.SUCCESS, "fetch_po"),
        Task(TaskStatus.FAILED, "fetch_po"),
    ]
    today_total = len(tasks)
    completed_today = sum(1 for t in tasks if t.status == TaskStatus.SUCCESS)
    success_rate = round(completed_today / max(today_total, 1) * 100, 2)
    assert success_rate == 50.0
