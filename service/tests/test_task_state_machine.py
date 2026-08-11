import pytest

from app.core.exceptions import BadRequestError
from app.models.automation_task import AutomationTask
from app.models.enums import TaskStatus
from app.services.task_state_machine import can_transition, transition


def test_task_state_machine_happy_path():
    task = AutomationTask(
        tenant_id="t1",
        title="demo",
        task_type="fetch_po",
        portal_account_id="p1",
        workflow_binding_id="b1",
        entity_type="CUSTOMER",
        erp_entity_code="C1",
        erp_entity_name="客户",
        status=TaskStatus.DRAFT,
        created_by="u1",
    )
    assert can_transition(TaskStatus.DRAFT, TaskStatus.READY)
    transition(task, TaskStatus.READY)
    transition(task, TaskStatus.QUEUED)
    transition(task, TaskStatus.LEASED)
    transition(task, TaskStatus.RUNNING)
    transition(task, TaskStatus.SUCCESS)
    assert task.status == TaskStatus.SUCCESS


def test_task_state_machine_invalid_transition():
    task = AutomationTask(
        tenant_id="t1",
        title="demo",
        task_type="fetch_po",
        portal_account_id="p1",
        workflow_binding_id="b1",
        entity_type="CUSTOMER",
        erp_entity_code="C1",
        erp_entity_name="客户",
        status=TaskStatus.DRAFT,
        created_by="u1",
    )
    with pytest.raises(BadRequestError):
        transition(task, TaskStatus.SUCCESS)
