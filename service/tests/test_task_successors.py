"""Engine 输出持久化与 Task 后继任务机制测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestError
from app.models.automation_task import AutomationTask
from app.models.enums import RunStatus, TaskStatus
from app.models.portal_account import PortalAccount
from app.models.rpa_run import RpaRun
from app.models.task_successor_job import TaskSuccessorJob
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.schemas.dispatch import RunFinishRequest
from app.services import dispatch_service
from app.services.task_successor_service import (
    SuccessorJobError,
    SuccessorJobProcessor,
    map_attachment_upload_input,
    map_delivery_confirmation_input,
    retry_successor_job,
    validate_delivery_confirmation_input,
    validate_successor_binding_config,
)


def source_output() -> dict:
    return {
        "schemaVersion": "ORDER_DOWNLOAD_PUSH_OUTPUT_V1",
        "poNo": "PO-001",
        "orderNumber": "ORDER-001",
        "supplierCode": "SUP-001",
        "supplierName": "供应商一",
        "lineCount": 2,
        "lines": [
            {
                "lineNumber": "10",
                "customerItemNumber": "MAT-001",
                "itemName": "物料一",
                "itemSpecification": "规格一",
                "orderQuantity": "5",
                "orderQuantityUom": "件",
                "requestDate": "2026-08-01",
                "standardDeliveryDays": "7",
            },
            {
                "lineNumber": "20",
                "customerItemNumber": "MAT-001",
                "itemName": "同料号第二行",
            },
        ],
    }


def delivery_confirmation_output() -> dict:
    return {
        "schemaVersion": "ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1",
        "poNo": "PO-001",
        "lineCount": 2,
        "saved": True,
        "signed": True,
        "replyStatus": "已回签",
        "lines": [],
    }


def test_finish_request_allows_output_only_for_success() -> None:
    body = RunFinishRequest(status="SUCCESS", output=source_output())
    assert body.output == source_output()

    with pytest.raises(ValidationError):
        RunFinishRequest(status="FAILED", output=source_output())


def test_mapper_creates_independent_blank_delivery_dates() -> None:
    result = map_delivery_confirmation_input(
        source_output(),
        source_task_id="task-1",
        source_run_id="run-1",
    )

    assert result["po_no"] == "PO-001"
    assert result["source_task_id"] == "task-1"
    assert result["source_run_id"] == "run-1"
    assert [line["line_number"] for line in result["order_lines"]] == [
        "10",
        "20",
    ]
    assert [line["material_number"] for line in result["order_lines"]] == [
        "MAT-001",
        "MAT-001",
    ]
    assert all(line["expected_delivery_date"] is None for line in result["order_lines"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(schemaVersion="UNKNOWN"),
        lambda value: value.update(lineCount=1),
        lambda value: value["lines"][1].update(lineNumber="10"),
        lambda value: value["lines"][0].update(customerItemNumber=""),
    ],
)
def test_mapper_rejects_invalid_source_output(mutate) -> None:
    value = source_output()
    mutate(value)
    with pytest.raises(SuccessorJobError):
        map_delivery_confirmation_input(
            value,
            source_task_id="task-1",
            source_run_id="run-1",
        )


def test_attachment_mapper_accepts_signed_delivery_confirmation() -> None:
    assert map_attachment_upload_input(delivery_confirmation_output()) == {"po_no": "PO-001"}


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    [
        ("schemaVersion", "UNKNOWN", "SUCCESSOR_OUTPUT_SCHEMA_UNSUPPORTED"),
        ("signed", False, "SUCCESSOR_OUTPUT_NOT_SIGNED"),
        (
            "replyStatus",
            "待签章",
            "SUCCESSOR_OUTPUT_REPLY_STATUS_INVALID",
        ),
        ("poNo", "", "SUCCESSOR_OUTPUT_INVALID"),
    ],
)
def test_attachment_mapper_rejects_unconfirmed_output(
    field: str,
    value,
    error_code: str,
) -> None:
    output = delivery_confirmation_output()
    output[field] = value

    with pytest.raises(SuccessorJobError) as captured:
        map_attachment_upload_input(output)

    assert captured.value.code == error_code


def test_delivery_confirmation_input_accepts_calendar_dates() -> None:
    value = map_delivery_confirmation_input(
        source_output(),
        source_task_id="task-1",
        source_run_id="run-1",
    )
    value["order_lines"][0]["expected_delivery_date"] = "2026-02-28"
    value["order_lines"][1]["expected_delivery_date"] = "2024-02-29"

    validate_delivery_confirmation_input(value)


@pytest.mark.parametrize(
    "invalid_date",
    [None, "", "2026-2-01", "2026-02-30", "not-a-date"],
)
def test_delivery_confirmation_input_rejects_missing_or_invalid_dates(
    invalid_date,
) -> None:
    value = map_delivery_confirmation_input(
        source_output(),
        source_task_id="task-1",
        source_run_id="run-1",
    )
    value["order_lines"][0]["expected_delivery_date"] = invalid_date
    value["order_lines"][1]["expected_delivery_date"] = "2026-03-01"

    with pytest.raises(BadRequestError):
        validate_delivery_confirmation_input(value)


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _list_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_success_finish_persists_output_and_enqueues_job(monkeypatch) -> None:
    run = RpaRun(
        id="run-1",
        task_id="task-1",
        rpa_flow_id="flow-1",
        status=RunStatus.RUNNING,
        rpa_worker_id=None,
    )
    task = AutomationTask(
        id="task-1",
        tenant_id="tenant-1",
        title="任务一",
        task_type="srm_prepare_erp_order",
        portal_account_id="portal-1",
        workflow_binding_id="binding-1",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        status=TaskStatus.RUNNING,
        priority="NORMAL",
        input="{}",
        created_by="user-1",
    )
    binding = WorkflowBinding(
        id="binding-1",
        portal_account_id="portal-1",
        workflow_template_id="template-1",
        workflow_template_version="1.0.0",
        rpa_flow_id="flow-1",
        rpa_flow_version="1.2.0",
        status="ENABLED",
        config="{}",
        created_by="user-1",
    )
    enqueue = AsyncMock()
    monkeypatch.setattr(dispatch_service, "enqueue_successor_job", enqueue)
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(run),
            _scalar_result(task),
            _scalar_result(binding),
            _list_result([]),
        ]
    )
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    finished = await dispatch_service.finish_run(
        db,
        "run-1",
        RunFinishRequest(status="SUCCESS", output=source_output()),
    )

    assert finished is run
    assert run.output == source_output()
    assert run.ended_at is not None
    assert task.status == TaskStatus.SUCCESS
    assert task.progress == 100
    enqueue.assert_awaited_once_with(
        db,
        source_task=task,
        source_run=run,
        source_binding=binding,
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_success_finish_replay_does_not_enqueue_again(monkeypatch) -> None:
    run = RpaRun(
        id="run-1",
        task_id="task-1",
        rpa_flow_id="flow-1",
        status=RunStatus.SUCCESS,
        output=source_output(),
    )
    task = AutomationTask(
        id="task-1",
        tenant_id="tenant-1",
        title="任务一",
        task_type="srm_prepare_erp_order",
        portal_account_id="portal-1",
        workflow_binding_id="binding-1",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        status=TaskStatus.SUCCESS,
        priority="NORMAL",
        input="{}",
        created_by="user-1",
    )
    enqueue = AsyncMock()
    monkeypatch.setattr(dispatch_service, "enqueue_successor_job", enqueue)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(run), _scalar_result(task)])
    db.commit = AsyncMock()

    finished = await dispatch_service.finish_run(
        db,
        "run-1",
        RunFinishRequest(status="SUCCESS", output=source_output()),
    )

    assert finished is run
    enqueue.assert_not_awaited()
    db.commit.assert_not_awaited()


def test_successor_job_model_has_idempotency_index() -> None:
    index = next(
        item for item in TaskSuccessorJob.__table__.indexes if item.name == "uq_task_successor_jobs_source_run_target"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "source_run_id",
        "target_workflow_binding_id",
    ]


@pytest.mark.asyncio
async def test_successor_binding_validation_accepts_exact_target() -> None:
    target = WorkflowBinding(
        id="binding-2",
        portal_account_id="portal-1",
        workflow_template_id="template-2",
        workflow_template_version="1.0.0",
        rpa_flow_id="delivery-flow",
        rpa_flow_version="1.0.0",
        rpa_flow_version_id="flow-version-2",
        flow_checksum_snapshot="a" * 64,
        status="ENABLED",
        config="{}",
        created_by="user-1",
    )
    portal = PortalAccount(
        id="portal-1",
        tenant_id="tenant-1",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        portal_name="SRM",
        portal_url="https://portal.example.com",
        login_account="user",
        credential_ref="credential-ref",
        status="ENABLED",
        created_by="user-1",
    )
    template = WorkflowTemplate(
        id="template-2",
        tenant_id="tenant-1",
        name="填写交货日期",
        code="srm_update_expected_delivery_dates",
        entity_type="CUSTOMER",
        status="ENABLED",
        created_by="user-1",
    )
    result = MagicMock()
    result.one_or_none.return_value = (target, portal, template)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    await validate_successor_binding_config(
        db,
        tenant_id="tenant-1",
        source_portal_account_id="portal-1",
        source_binding_id="binding-1",
        config={
            "successor": {
                "on": "SUCCESS",
                "targetWorkflowBindingId": "binding-2",
                "inputMapper": "ORDER_DELIVERY_CONFIRMATION_V1",
            }
        },
    )


@pytest.mark.asyncio
async def test_successor_binding_validation_accepts_attachment_target() -> None:
    target = WorkflowBinding(
        id="binding-3",
        portal_account_id="portal-1",
        workflow_template_id="template-3",
        workflow_template_version="1.0.0",
        rpa_flow_id="attachment-flow",
        rpa_flow_version="1.0.0",
        rpa_flow_version_id="flow-version-3",
        flow_checksum_snapshot="b" * 64,
        status="ENABLED",
        config="{}",
        created_by="user-1",
    )
    portal = PortalAccount(
        id="portal-1",
        tenant_id="tenant-1",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        portal_name="SRM",
        portal_url="https://portal.example.com",
        login_account="user",
        credential_ref="credential-ref",
        status="ENABLED",
        created_by="user-1",
    )
    template = WorkflowTemplate(
        id="template-3",
        tenant_id="tenant-1",
        name="上传订单附件",
        code="srm_upload_order_attachment",
        entity_type="CUSTOMER",
        status="ENABLED",
        created_by="user-1",
    )
    result = MagicMock()
    result.one_or_none.return_value = (target, portal, template)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    await validate_successor_binding_config(
        db,
        tenant_id="tenant-1",
        source_portal_account_id="portal-1",
        source_binding_id="binding-2",
        config={
            "successor": {
                "on": "SUCCESS",
                "targetWorkflowBindingId": "binding-3",
                "inputMapper": "ORDER_ATTACHMENT_UPLOAD_V1",
            }
        },
    )


@pytest.mark.asyncio
async def test_successor_binding_validation_rejects_self_reference() -> None:
    db = MagicMock()
    db.execute = AsyncMock()
    with pytest.raises(BadRequestError) as captured:
        await validate_successor_binding_config(
            db,
            tenant_id="tenant-1",
            source_portal_account_id="portal-1",
            source_binding_id="binding-1",
            config={
                "successor": {
                    "on": "SUCCESS",
                    "targetWorkflowBindingId": "binding-1",
                    "inputMapper": "ORDER_DELIVERY_CONFIRMATION_V1",
                }
            },
        )
    assert captured.value.message_key == ("errors.autotask.successor_binding_self_reference")
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_processor_creates_draft_successor_with_source_links() -> None:
    source_task = AutomationTask(
        id="task-1",
        tenant_id="tenant-1",
        title="任务一",
        task_type="srm_prepare_erp_order",
        portal_account_id="portal-1",
        workflow_binding_id="binding-1",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        status=TaskStatus.SUCCESS,
        priority="HIGH",
        input="{}",
        created_by="user-1",
        assigned_to=None,
    )
    source_run = RpaRun(
        id="run-1",
        task_id="task-1",
        rpa_flow_id="flow-1",
        status=RunStatus.SUCCESS,
        output=source_output(),
    )
    target = WorkflowBinding(
        id="binding-2",
        portal_account_id="portal-1",
        workflow_template_id="template-2",
        workflow_template_version="1.0.0",
        rpa_flow_id="delivery-flow",
        rpa_flow_version="1.0.0",
        rpa_flow_version_id="flow-version-2",
        flow_checksum_snapshot="a" * 64,
        status="ENABLED",
        config="{}",
        created_by="user-1",
    )
    portal = MagicMock()
    template = WorkflowTemplate(
        id="template-2",
        tenant_id="tenant-1",
        name="填写交货日期",
        code="srm_update_expected_delivery_dates",
        entity_type="CUSTOMER",
        status="ENABLED",
        created_by="user-1",
    )
    job = TaskSuccessorJob(
        id="job-1",
        tenant_id="tenant-1",
        source_task_id="task-1",
        source_run_id="run-1",
        target_workflow_binding_id="binding-2",
        input_mapper="ORDER_DELIVERY_CONFIRMATION_V1",
        status="PROCESSING",
        attempt_count=1,
    )
    target_result = MagicMock()
    target_result.one_or_none.return_value = (target, portal, template)
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(source_task),
            _scalar_result(source_run),
            target_result,
        ]
    )
    added: list[object] = []
    db.add.side_effect = added.append

    async def flush() -> None:
        child = next(item for item in added if isinstance(item, AutomationTask))
        child.id = "task-2"

    db.flush = AsyncMock(side_effect=flush)
    processor = object.__new__(SuccessorJobProcessor)

    await processor._create_successor_task(db, job)  # noqa: SLF001

    child = next(item for item in added if isinstance(item, AutomationTask))
    assert child.status == TaskStatus.DRAFT
    assert child.workflow_binding_id == "binding-2"
    assert child.source_task_id == "task-1"
    assert child.source_run_id == "run-1"
    assert child.assigned_to == "user-1"
    assert all(line["expected_delivery_date"] is None for line in __import__("json").loads(child.input)["order_lines"])
    assert job.status == "SUCCEEDED"
    assert job.successor_task_id == "task-2"


@pytest.mark.asyncio
async def test_processor_queues_attachment_successor_with_run() -> None:
    source_task = AutomationTask(
        id="task-2",
        tenant_id="tenant-1",
        title="任务二",
        task_type="srm_update_expected_delivery_dates",
        portal_account_id="portal-1",
        workflow_binding_id="binding-2",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        status=TaskStatus.SUCCESS,
        priority="HIGH",
        input="{}",
        created_by="user-1",
        assigned_to="user-1",
    )
    source_run = RpaRun(
        id="run-2",
        task_id="task-2",
        rpa_flow_id="delivery-flow",
        status=RunStatus.SUCCESS,
        output=delivery_confirmation_output(),
    )
    target = WorkflowBinding(
        id="binding-3",
        portal_account_id="portal-1",
        workflow_template_id="template-3",
        workflow_template_version="1.0.0",
        rpa_flow_id="attachment-flow",
        rpa_flow_version="1.0.0",
        rpa_flow_version_id="flow-version-3",
        flow_checksum_snapshot="b" * 64,
        status="ENABLED",
        config="{}",
        created_by="user-1",
    )
    template = WorkflowTemplate(
        id="template-3",
        tenant_id="tenant-1",
        name="上传订单附件",
        code="srm_upload_order_attachment",
        entity_type="CUSTOMER",
        status="ENABLED",
        created_by="user-1",
    )
    job = TaskSuccessorJob(
        id="job-2",
        tenant_id="tenant-1",
        source_task_id="task-2",
        source_run_id="run-2",
        target_workflow_binding_id="binding-3",
        input_mapper="ORDER_ATTACHMENT_UPLOAD_V1",
        status="PROCESSING",
        attempt_count=1,
    )
    target_result = MagicMock()
    target_result.one_or_none.return_value = (target, MagicMock(), template)
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(source_task),
            _scalar_result(source_run),
            target_result,
        ]
    )
    added: list[object] = []
    db.add.side_effect = added.append

    async def flush() -> None:
        child = next(item for item in added if isinstance(item, AutomationTask))
        child.id = "task-3"

    db.flush = AsyncMock(side_effect=flush)
    processor = object.__new__(SuccessorJobProcessor)

    await processor._create_successor_task(db, job)  # noqa: SLF001

    child = next(item for item in added if isinstance(item, AutomationTask))
    run = next(item for item in added if isinstance(item, RpaRun))
    assert child.title == "3. 上传订单附件 - PO-001"
    assert child.status == TaskStatus.QUEUED
    assert child.workflow_binding_id == "binding-3"
    assert child.source_task_id == "task-2"
    assert child.source_run_id == "run-2"
    assert __import__("json").loads(child.input) == {"po_no": "PO-001"}
    assert run.task_id == "task-3"
    assert run.rpa_flow_id == "attachment-flow"
    assert run.status == RunStatus.QUEUED
    assert job.status == "SUCCEEDED"
    assert job.successor_task_id == "task-3"


@pytest.mark.asyncio
async def test_manual_retry_resets_failed_successor_job() -> None:
    job = TaskSuccessorJob(
        id="job-1",
        tenant_id="tenant-1",
        source_task_id="task-1",
        source_run_id="run-1",
        target_workflow_binding_id="binding-2",
        input_mapper="ORDER_DELIVERY_CONFIRMATION_V1",
        status="FAILED",
        attempt_count=10,
        last_error_code="SUCCESSOR_BINDING_DISABLED",
        last_error_message="disabled",
    )
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(job))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await retry_successor_job(
        db,
        tenant_id="tenant-1",
        source_task_id="task-1",
        job_id="job-1",
    )

    assert result.status == "PENDING"
    assert result.attempt_count == 0
    assert result.next_attempt_at is not None
    assert result.last_error_code is None
    db.commit.assert_awaited_once()
