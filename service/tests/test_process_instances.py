"""流程实例（SOP 主任务）服务测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.enums import ProcessInstanceStatus, ProcessLineStatus, ProcessStage, RunStatus
from app.models.process_instance import ProcessInstance
from app.models.process_line_item import ProcessLineItem
from app.models.process_stage_history import ProcessStageHistory
from app.models.rpa_run import RpaRun
from app.models.automation_task import AutomationTask
from app.services import process_instance_service as svc


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _instance(**overrides) -> ProcessInstance:
    defaults = {
        "id": "inst-1",
        "tenant_id": "tenant-1",
        "process_code": svc.PROCESS_CODE_SRM_CUSTOMER_ORDER,
        "biz_key": "PO-001",
        "title": "客户订单处理 - PO-001",
        "portal_account_id": "portal-1",
        "stage": ProcessStage.SDMS_CREATED.value,
        "status": ProcessInstanceStatus.ACTIVE.value,
        "line_total": 2,
        "line_done": 0,
        "summary": "{}",
        "created_by": "user-1",
    }
    defaults.update(overrides)
    return ProcessInstance(**defaults)


def _line(line_number: str, status: str = ProcessLineStatus.PENDING.value) -> ProcessLineItem:
    return ProcessLineItem(
        id=f"line-{line_number}",
        instance_id="inst-1",
        line_number=line_number,
        material_number="MAT-001",
        line_status=status,
    )


def _user(user_id: str = "user-1"):
    user = MagicMock()
    user.user_id = user_id
    return user


def test_valid_date() -> None:
    assert svc._valid_date("2026-08-15") is True
    assert svc._valid_date("2026-13-01") is False
    assert svc._valid_date("20260815") is False
    assert svc._valid_date("") is False


def test_stage_definitions_cover_all_stages() -> None:
    defined = {item["id"] for item in svc.STAGE_DEFINITIONS}
    assert defined == {stage.value for stage in ProcessStage}


@pytest.mark.asyncio
async def test_submit_line_date_rejects_wrong_stage() -> None:
    instance = _instance(stage=ProcessStage.CREATING_SDMS.value)
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(instance))
    with pytest.raises(BadRequestError):
        await svc.submit_line_date(db, "tenant-1", "inst-1", "10", "2026-08-15", _user())


@pytest.mark.asyncio
async def test_submit_line_date_rejects_invalid_date() -> None:
    instance = _instance()
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(instance))
    with pytest.raises(BadRequestError):
        await svc.submit_line_date(db, "tenant-1", "inst-1", "10", "08/15", _user())


@pytest.mark.asyncio
async def test_submit_line_date_rejects_submitting_line() -> None:
    instance = _instance()
    line = _line("10", ProcessLineStatus.SUBMITTING.value)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(instance), _scalar_result(line)])
    with pytest.raises(BadRequestError):
        await svc.submit_line_date(db, "tenant-1", "inst-1", "10", "2026-08-15", _user())


@pytest.mark.asyncio
async def test_submit_line_date_line_not_found() -> None:
    instance = _instance()
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(instance), _scalar_result(None)])
    with pytest.raises(NotFoundError):
        await svc.submit_line_date(db, "tenant-1", "inst-1", "99", "2026-08-15", _user())


@pytest.mark.asyncio
async def test_request_sign_requires_dates_complete() -> None:
    instance = _instance(stage=ProcessStage.DATES_PARTIAL.value)
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(instance))
    with pytest.raises(BadRequestError):
        await svc.request_sign(db, "tenant-1", "inst-1", _user())


@pytest.mark.asyncio
async def test_request_sign_passes_temp_e2e_backfill_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """TEMP_E2E_ONLY: 签章子任务需带 AutoTask 已写交期，供 Flow 签章前回填。联调后删除本测。"""
    instance = _instance(stage=ProcessStage.DATES_COMPLETE.value)
    lines = [
        ProcessLineItem(
            id="line-10",
            instance_id="inst-1",
            line_number="10",
            material_number="MAT-001",
            line_status=ProcessLineStatus.WRITTEN.value,
            expected_delivery_date="2026-09-15",
        ),
        ProcessLineItem(
            id="line-20",
            instance_id="inst-1",
            line_number="20",
            material_number="MAT-002",
            line_status=ProcessLineStatus.WRITTEN.value,
            expected_delivery_date="2026-09-20",
        ),
    ]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(instance), _scalars_result(lines)])
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    captured: dict = {}

    async def _fake_create_sub_task(db_arg, inst, **kwargs):  # noqa: ANN001
        captured.update(kwargs)
        task = MagicMock()
        task.id = "task-sign-1"
        return task

    monkeypatch.setattr(svc, "_create_sub_task", _fake_create_sub_task)
    await svc.request_sign(db, "tenant-1", "inst-1", _user())
    assert captured["template_code"] == svc.SIGN_TEMPLATE_CODE
    assert captured["task_input"]["po_no"] == "PO-001"
    assert captured["task_input"]["temp_e2e_backfill_dates"] is True
    assert captured["task_input"]["order_lines"] == [
        {"line_number": "10", "expected_delivery_date": "2026-09-15"},
        {"line_number": "20", "expected_delivery_date": "2026-09-20"},
    ]


@pytest.mark.asyncio
async def test_archive_rejects_sign_requested_and_dates_complete() -> None:
    """待回签/待签章不可手动下载合同；仅 SIGNED 可兜底。"""
    for stage in (ProcessStage.DATES_COMPLETE.value, ProcessStage.SIGN_REQUESTED.value):
        instance = _instance(stage=stage)
        db = MagicMock()
        db.execute = AsyncMock(return_value=_scalar_result(instance))
        with pytest.raises(BadRequestError):
            await svc.archive_signed_order(db, "tenant-1", "inst-1", _user())


@pytest.mark.asyncio
async def test_retry_requires_failed_status() -> None:
    instance = _instance(status=ProcessInstanceStatus.ACTIVE.value)
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(instance))
    with pytest.raises(BadRequestError):
        await svc.retry_instance(db, "tenant-1", "inst-1", _user())


@pytest.mark.asyncio
async def test_create_sdms_failure_fails_instance() -> None:
    instance = _instance(stage=ProcessStage.CREATING_SDMS.value)
    run = RpaRun(
        id="run-1",
        task_id="task-1",
        rpa_flow_id="flow-1",
        status=RunStatus.FAILED,
        error_code="ERP_ORDER_IMPORT_ROW_FAILED",
        error_message="ERP 行级失败",
    )
    db = MagicMock()
    db.add = MagicMock()
    await svc._handle_create_sdms_finished(db, instance, run, succeeded=False)

    assert instance.status == ProcessInstanceStatus.FAILED.value
    assert instance.stage == ProcessStage.FAILED.value
    assert instance.last_error_code == "ERP_ORDER_IMPORT_ROW_FAILED"
    history = next(item for item in db.add.call_args_list if isinstance(item.args[0], ProcessStageHistory))
    assert history.args[0].to_stage == ProcessStage.FAILED.value


@pytest.mark.asyncio
async def test_create_sdms_success_creates_lines_and_advances() -> None:
    instance = _instance(stage=ProcessStage.CREATING_SDMS.value, line_total=0)
    run = RpaRun(
        id="run-1",
        task_id="task-1",
        rpa_flow_id="flow-1",
        status=RunStatus.SUCCESS,
        output={
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
                    "itemSpecification": "规格A",
                    "materialStatus": "正常",
                    "internalCode": "IC-1",
                    "orderQuantity": "100",
                    "orderQuantityUom": "PCS",
                    "unitSellingPrice": "1.5",
                    "taxIncludedAmount": "150",
                    "requestDate": "2026-08-01",
                    "standardDeliveryDays": "7",
                    "meetsLeadTime": "是",
                    "supplierDeliveryDate": "2026-08-10",
                    "outstandingQuantity": "100",
                    "remarks": "备注一",
                    "directShipmentRemarks": "直发备注",
                },
                {"lineNumber": "20", "customerItemNumber": "MAT-002"},
            ],
        },
    )
    added: list[object] = []
    db = MagicMock()
    db.add = MagicMock(side_effect=added.append)
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        return_value=_scalars_result([item for item in added if isinstance(item, ProcessLineItem)])
    )

    await svc._handle_create_sdms_finished(db, instance, run, succeeded=True)

    lines = [item for item in added if isinstance(item, ProcessLineItem)]
    assert [line.line_number for line in lines] == ["10", "20"]
    assert lines[0].item_specification == "规格A"
    assert lines[0].material_status == "正常"
    assert lines[0].unit_selling_price == "1.5"
    assert lines[0].remarks == "备注一"
    assert all(line.line_status == ProcessLineStatus.PENDING.value for line in lines)
    assert instance.stage == ProcessStage.SDMS_CREATED.value
    assert instance.status == ProcessInstanceStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_fill_line_success_marks_written_and_completes() -> None:
    instance = _instance(stage=ProcessStage.DATES_PARTIAL.value, line_total=2, line_done=1)
    line10 = _line("10", ProcessLineStatus.WRITTEN.value)
    line20 = _line("20", ProcessLineStatus.SUBMITTING.value)
    task = AutomationTask(
        id="task-fill",
        tenant_id="tenant-1",
        title="填写交货日期",
        task_type=svc.FILL_LINE_DATE_TEMPLATE_CODE,
        portal_account_id="portal-1",
        workflow_binding_id="binding-1",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        status="SUCCESS",
        input='{"po_no": "PO-001", "line_number": "20", "expected_delivery_date": "2026-08-20"}',
        created_by="user-1",
    )
    run = RpaRun(id="run-2", task_id="task-fill", rpa_flow_id="flow-1", status=RunStatus.SUCCESS)
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(line20),
            _scalars_result([line10, line20]),
        ]
    )

    await svc._handle_fill_line_finished(db, instance, task, run, succeeded=True)

    assert line20.line_status == ProcessLineStatus.WRITTEN.value
    assert instance.line_done == 2
    assert instance.stage == ProcessStage.DATES_COMPLETE.value


@pytest.mark.asyncio
async def test_fill_line_failure_marks_line_failed_without_rollback() -> None:
    instance = _instance(stage=ProcessStage.DATES_PARTIAL.value, line_total=2, line_done=1)
    line10 = _line("10", ProcessLineStatus.WRITTEN.value)
    line20 = _line("20", ProcessLineStatus.SUBMITTING.value)
    task = AutomationTask(
        id="task-fill",
        tenant_id="tenant-1",
        title="填写交货日期",
        task_type=svc.FILL_LINE_DATE_TEMPLATE_CODE,
        portal_account_id="portal-1",
        workflow_binding_id="binding-1",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        status="FAILED",
        input='{"po_no": "PO-001", "line_number": "20"}',
        created_by="user-1",
    )
    run = RpaRun(
        id="run-3",
        task_id="task-fill",
        rpa_flow_id="flow-1",
        status=RunStatus.FAILED,
        error_code="ORDER_NOT_EDITABLE",
        error_message="行不可编辑",
    )
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(line20),
            _scalars_result([line10, line20]),
        ]
    )

    await svc._handle_fill_line_finished(db, instance, task, run, succeeded=False)

    assert line20.line_status == ProcessLineStatus.WRITE_FAILED.value
    assert line20.last_error_code == "ORDER_NOT_EDITABLE"
    assert line10.line_status == ProcessLineStatus.WRITTEN.value
    assert instance.status == ProcessInstanceStatus.ACTIVE.value
    assert instance.line_done == 1
    assert instance.stage == ProcessStage.DATES_PARTIAL.value


@pytest.mark.asyncio
async def test_sign_success_moves_to_sign_requested() -> None:
    instance = _instance(stage=ProcessStage.DATES_COMPLETE.value)
    instance.last_error_code = "ORDER_SIGN_STATUS_UNCONFIRMED"
    instance.last_error_message = "Order reply status was not confirmed after sign"
    run = RpaRun(id="run-4", task_id="task-sign", rpa_flow_id="flow-1", status=RunStatus.SUCCESS)
    db = MagicMock()
    db.add = MagicMock()

    await svc._handle_sign_finished(db, instance, run, succeeded=True)

    assert instance.stage == ProcessStage.SIGN_REQUESTED.value
    assert instance.last_error_code is None
    assert instance.last_error_message is None


@pytest.mark.asyncio
async def test_archive_success_completes_instance() -> None:
    instance = _instance(stage=ProcessStage.SIGNED.value)
    instance.last_error_code = "ORDER_SIGN_STATUS_UNCONFIRMED"
    instance.last_error_message = "stale"
    run = RpaRun(id="run-5", task_id="task-archive", rpa_flow_id="flow-1", status=RunStatus.SUCCESS)
    db = MagicMock()
    db.add = MagicMock()

    await svc._handle_archive_finished(db, instance, run, succeeded=True)

    assert instance.stage == ProcessStage.ARCHIVED.value
    assert instance.status == ProcessInstanceStatus.COMPLETED.value
    assert instance.last_error_code is None
    assert instance.last_error_message is None


@pytest.mark.asyncio
async def test_sign_failure_stores_chinese_error() -> None:
    instance = _instance(stage=ProcessStage.DATES_COMPLETE.value)
    run = RpaRun(
        id="run-sign-fail",
        task_id="task-sign",
        rpa_flow_id="flow-1",
        status=RunStatus.WAITING_HUMAN,
        error_code="ORDER_SIGN_STATUS_UNCONFIRMED",
        error_message="Order reply status was not confirmed after sign",
    )
    db = MagicMock()

    await svc._handle_sign_finished(db, instance, run, succeeded=False)

    assert instance.last_error_code == "ORDER_SIGN_STATUS_UNCONFIRMED"
    assert "签章后未能确认" in (instance.last_error_message or "")


@pytest.mark.asyncio
async def test_on_sub_task_finished_ignores_unrelated_tasks() -> None:
    task = AutomationTask(
        id="task-old",
        tenant_id="tenant-1",
        title="旧链任务",
        task_type=svc.CREATE_SDMS_TEMPLATE_CODE,
        portal_account_id="portal-1",
        workflow_binding_id="binding-1",
        entity_type="CUSTOMER",
        erp_entity_code="ERP-1",
        erp_entity_name="客户一",
        status="SUCCESS",
        input="{}",
        created_by="user-1",
        process_instance_id=None,
    )
    run = RpaRun(id="run-6", task_id="task-old", rpa_flow_id="flow-1", status=RunStatus.SUCCESS)
    db = MagicMock()
    db.execute = AsyncMock()

    await svc.on_sub_task_finished(db, task, run)

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_success_with_signed_reply_stays_for_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """演示门户签章瞬间可能返回已回签，也不得立即归档；交给轮询。"""
    instance = _instance(stage=ProcessStage.DATES_COMPLETE.value)
    run = RpaRun(
        id="run-4",
        task_id="task-sign",
        rpa_flow_id="flow-1",
        status=RunStatus.SUCCESS,
        output={"replyStatus": "已回签"},
    )
    db = MagicMock()
    db.add = MagicMock()
    called: dict = {}

    async def _fake_trigger(db_arg, inst, **kwargs):  # noqa: ANN001
        called.update(kwargs)
        called["instance_id"] = inst.id
        return True

    monkeypatch.setattr(svc, "_trigger_archive_if_needed", _fake_trigger)
    await svc._handle_sign_finished(db, instance, run, succeeded=True)
    assert instance.stage == ProcessStage.SIGN_REQUESTED.value
    assert called == {}


@pytest.mark.asyncio
async def test_check_reply_signed_triggers_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _instance(stage=ProcessStage.SIGN_REQUESTED.value)
    run = RpaRun(
        id="run-check",
        task_id="task-check",
        rpa_flow_id="flow-1",
        status=RunStatus.SUCCESS,
        output={"replyStatus": "已回签"},
    )
    db = MagicMock()
    called: dict = {}

    async def _fake_trigger(db_arg, inst, **kwargs):  # noqa: ANN001
        called.update(kwargs)
        return True

    monkeypatch.setattr(svc, "_trigger_archive_if_needed", _fake_trigger)
    await svc._handle_check_reply_finished(db, instance, run, succeeded=True)
    assert called["actor"] == "sign-poll-scheduler"


@pytest.mark.asyncio
async def test_check_reply_pending_does_not_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _instance(stage=ProcessStage.SIGN_REQUESTED.value)
    run = RpaRun(
        id="run-check",
        task_id="task-check",
        rpa_flow_id="flow-1",
        status=RunStatus.SUCCESS,
        output={"replyStatus": "待回签"},
    )
    db = MagicMock()
    called = False

    async def _fake_trigger(*_args, **_kwargs):  # noqa: ANN001
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(svc, "_trigger_archive_if_needed", _fake_trigger)
    await svc._handle_check_reply_finished(db, instance, run, succeeded=True)
    assert called is False


@pytest.mark.asyncio
async def test_trigger_archive_idempotent_skips_when_archive_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _instance(stage=ProcessStage.SIGN_REQUESTED.value)
    db = MagicMock()
    created = False

    async def _fake_has(*_args, **_kwargs):  # noqa: ANN001
        return True

    async def _fake_create(*_args, **_kwargs):  # noqa: ANN001
        nonlocal created
        created = True
        return MagicMock()

    monkeypatch.setattr(svc, "_has_archive_in_progress_or_success", _fake_has)
    monkeypatch.setattr(svc, "_create_sub_task", _fake_create)
    result = await svc._trigger_archive_if_needed(
        db, instance, actor="user-1", note="manual"
    )
    assert result is False
    assert created is False
    # 即使不新建归档任务，也要先进入已回签，便于手动重试
    assert instance.stage == ProcessStage.SIGNED.value


@pytest.mark.asyncio
async def test_create_check_reply_skips_non_poll_stages() -> None:
    instance = _instance(stage=ProcessStage.SDMS_CREATED.value)
    db = MagicMock()
    task = await svc.create_check_reply_task(db, instance, actor="sign-poll-scheduler")
    assert task is None


@pytest.mark.asyncio
async def test_create_check_reply_allows_dates_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _instance(stage=ProcessStage.DATES_COMPLETE.value)
    db = MagicMock()
    fake = MagicMock(id="task-check")

    async def _create(*_a, **_k):  # noqa: ANN001
        return fake

    async def _no(*_a, **_k):  # noqa: ANN001
        return False

    monkeypatch.setattr(svc, "_create_sub_task", _create)
    monkeypatch.setattr(svc, "_has_check_reply_in_flight", _no)
    monkeypatch.setattr(svc, "_has_archive_in_progress_or_success", _no)
    task = await svc.create_check_reply_task(db, instance, actor="sign-poll-scheduler")
    assert task is fake


@pytest.mark.asyncio
async def test_trigger_archive_from_dates_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _instance(stage=ProcessStage.DATES_COMPLETE.value)
    db = MagicMock()
    db.add = MagicMock()

    async def _no(*_a, **_k):  # noqa: ANN001
        return False

    async def _create(*_a, **_k):  # noqa: ANN001
        return MagicMock(id="task-arch")

    monkeypatch.setattr(svc, "_has_archive_in_progress_or_success", _no)
    monkeypatch.setattr(svc, "_create_sub_task", _create)
    ok = await svc._trigger_archive_if_needed(
        db, instance, actor="sign-poll-scheduler", note="poll"
    )
    assert ok is True
    assert instance.stage == ProcessStage.SIGNED.value


@pytest.mark.asyncio
async def test_sign_poll_scheduler_process_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings
    from app.services.sign_poll_scheduler import SignPollScheduler

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    def _factory():
        return _Session()

    async def _run(_db, **kwargs):  # noqa: ANN001
        assert kwargs["actor"] == "sign-poll-scheduler"
        return {"candidate_count": 2, "created_count": 1}

    monkeypatch.setattr(svc, "run_sign_poll_once", _run)

    scheduler = SignPollScheduler(_factory, Settings(SIGN_POLL_INTERVAL_SECONDS=1800))
    count = await scheduler.process_once()
    assert count == 1
