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
    defined = {
        item["id"]
        for stages in svc.STAGE_DEFINITIONS.values()
        for item in stages
    }
    assert defined == {stage.value for stage in ProcessStage}


@pytest.mark.asyncio
async def test_handle_scan_success_empty_orders_does_not_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = MagicMock()
    run = MagicMock()
    run.output = {"schemaVersion": svc.SCAN_OUTPUT_SCHEMA, "orders": []}
    created = False

    async def _create(*_a, **_k):  # noqa: ANN001
        nonlocal created
        created = True
        return []

    monkeypatch.setattr(svc, "create_from_scan", _create)
    await svc._handle_scan_success(MagicMock(), task, run)
    assert created is False


@pytest.mark.asyncio
async def test_handle_scan_success_marks_drill_from_flow_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = MagicMock()
    task.tenant_id = "tenant-1"
    task.portal_account_id = "portal-1"
    task.created_by = "user-1"
    run = MagicMock()
    run.output = {
        "schemaVersion": svc.SCAN_OUTPUT_SCHEMA,
        "orders": [{"poNo": "POJS2607170008", "replyStatus": "待签章"}],
        "source": "xlsx",
        "drill": {"assumedPending": True, "poNo": "POJS2607170008"},
    }
    instance = _instance(biz_key="POJS2607170008")
    instance.summary = "{}"
    captured: dict = {}

    async def _create(_db, _tenant, _portal_id, orders, **kwargs):  # noqa: ANN001
        captured["orders"] = orders
        captured["kwargs"] = kwargs
        return [instance]

    monkeypatch.setattr(svc, "create_from_scan", _create)
    await svc._handle_scan_success(MagicMock(), task, run)
    assert captured["orders"][0]["poNo"] == "POJS2607170008"
    assert captured["kwargs"]["allow_missing_prepare_binding"] is True
    from app.services.json_utils import loads_json

    summary = loads_json(instance.summary, {})
    assert summary["drill"]["assumedPending"] is True
    assert summary["poNo"] == "POJS2607170008"


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
    monkeypatch.setattr(svc, "_is_demo_portal", AsyncMock(return_value=True))
    await svc.request_sign(db, "tenant-1", "inst-1", _user())
    assert captured["template_code"] == svc.SIGN_TEMPLATE_CODE
    assert captured["task_input"]["po_no"] == "PO-001"
    assert captured["task_input"]["temp_e2e_backfill_dates"] is True
    assert captured["task_input"]["order_lines"] == [
        {"line_number": "10", "expected_delivery_date": "2026-09-15"},
        {"line_number": "20", "expected_delivery_date": "2026-09-20"},
    ]


@pytest.mark.asyncio
async def test_request_sign_skips_temp_e2e_backfill_on_official_portal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch.setattr(svc, "_is_demo_portal", AsyncMock(return_value=False))
    await svc.request_sign(db, "tenant-1", "inst-1", _user())
    assert captured["task_input"] == {"po_no": "PO-001"}


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
async def test_archive_requires_sdms_username() -> None:
    instance = _instance(stage=ProcessStage.SIGNED.value)
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(instance))
    user = _user()
    user.name = None
    with pytest.raises(BadRequestError) as captured:
        await svc.archive_signed_order(db, "tenant-1", "inst-1", user, sdms_username="")
    assert captured.value.message_key == "errors.autotask.sdms_username_missing"


@pytest.mark.asyncio
async def test_resolve_archive_username_uses_portal_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """轮询无登录人时，用门户归属人工号，而不是实例创建人。"""
    instance = _instance(created_by="creator-1", portal_account_id="portal-1")
    portal = MagicMock()
    portal.owner_user_id = "owner-1"
    portal.created_by = "creator-1"
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(portal))

    async def _owner_username(_db, user_id):
        assert user_id == "owner-1"
        return "OWNER-JOB-ID"

    monkeypatch.setattr(svc, "username_from_user_cache", _owner_username)
    username = await svc._resolve_archive_username(db, instance, "")
    assert username == "OWNER-JOB-ID"


@pytest.mark.asyncio
async def test_resolve_archive_username_uses_creator_without_portal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _instance(created_by="creator-1", portal_account_id=None)

    async def _creator_username(_db, user_id):
        assert user_id == "creator-1"
        return "CREATOR-JOB-ID"

    monkeypatch.setattr(svc, "username_from_user_cache", _creator_username)
    username = await svc._resolve_archive_username(MagicMock(), instance, "")
    assert username == "CREATOR-JOB-ID"


@pytest.mark.asyncio
async def test_resolve_archive_username_empty_when_cache_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """查不到工号时返回空，不再写死兜底工号。"""
    instance = _instance(created_by="scripts/seed_sign_poll_test", portal_account_id=None)

    async def _empty_username(_db, _user_id):
        return ""

    monkeypatch.setattr(svc, "username_from_user_cache", _empty_username)
    username = await svc._resolve_archive_username(MagicMock(), instance, "")
    assert username == ""


@pytest.mark.asyncio
async def test_resolve_archive_username_prefers_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _instance()

    async def _should_not_call(_db, _user_id):
        raise AssertionError("should not consult user cache when username provided")

    monkeypatch.setattr(svc, "username_from_user_cache", _should_not_call)
    assert await svc._resolve_archive_username(MagicMock(), instance, "explicit") == "explicit"



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

    async def _username(_db, _instance, _given):
        return "CREATOR-JOB-ID"

    monkeypatch.setattr(svc, "_resolve_archive_username", _username)
    await svc._handle_check_reply_finished(db, instance, run, succeeded=True)
    assert called["actor"] == "sign-poll-scheduler"
    assert called["sdms_username"] == "CREATOR-JOB-ID"


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
        db, instance, actor="user-1", note="manual", sdms_username="tester"
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
async def test_create_sub_task_rejects_disabled_portal() -> None:
    instance = _instance(stage=ProcessStage.SIGN_REQUESTED.value)
    portal = MagicMock()
    portal.status = "DISABLED"
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(portal))
    with pytest.raises(BadRequestError) as exc:
        await svc._create_sub_task(
            db,
            instance,
            template_code="srm_check_reply_status",
            title="回签探测 - PO-001",
            task_input={"po_no": "PO-001"},
            actor="sign-poll-scheduler",
        )
    assert exc.value.message_key == "errors.autotask.portal_disabled"


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

    captured: dict = {}

    async def _create(*_a, **kwargs):  # noqa: ANN001
        captured.update(kwargs)
        return MagicMock(id="task-arch")

    monkeypatch.setattr(svc, "_has_archive_in_progress_or_success", _no)
    monkeypatch.setattr(svc, "_create_sub_task", _create)
    ok = await svc._trigger_archive_if_needed(
        db, instance, actor="sign-poll-scheduler", note="poll", sdms_username="tester"
    )
    assert ok is True
    assert instance.stage == ProcessStage.SIGNED.value
    assert captured["task_input"] == {"po_no": "PO-001", "username": "tester"}


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


@pytest.mark.asyncio
async def test_scan_scheduler_only_targets_portals_with_enabled_scan_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """定时扫单只对拥有 ENABLED srm_scan_pending_orders 绑定的门户建任务。"""
    from datetime import datetime

    from app.core.config import Settings
    from app.services import scan_scheduler as sched_mod
    from app.services.scan_scheduler import ScanScheduler

    captured_portal_ids: list[str] = []

    portal_with_binding = MagicMock(id="portal-bound", tenant_id="tenant-1")

    class _Result:
        def scalars(self):
            class _S:
                def all(self):
                    return [portal_with_binding]

            return _S()

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, _stmt):
            return _Result()

        async def rollback(self):
            return None

    def _factory():
        return _Session()

    async def _create_scan_task(_db, _tenant, portal_account_id, *, actor):
        captured_portal_ids.append(portal_account_id)
        return MagicMock()

    # patch the name imported into the scheduler module
    monkeypatch.setattr(sched_mod, "create_scan_task", _create_scan_task)
    monkeypatch.setattr(
        sched_mod,
        "datetime",
        MagicMock(now=lambda: datetime(2026, 8, 19, 9, 5)),
    )

    scheduler = ScanScheduler(_factory, Settings())
    scheduler._last_run_date = None
    count = await scheduler.process_once()
    assert count == 1
    assert captured_portal_ids == ["portal-bound"]


@pytest.mark.asyncio
async def test_ensure_prepare_sub_task_creates_when_stuck_without_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _instance(stage=ProcessStage.CREATING_SDMS.value, biz_key="POJS2607170008")
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(None))
    captured: dict = {}

    async def _create(_db, inst, **kwargs):  # noqa: ANN001
        captured["instance"] = inst
        captured.update(kwargs)
        return MagicMock(id="task-prepare")

    monkeypatch.setattr(svc, "_create_sub_task", _create)
    task = await svc._ensure_prepare_sub_task(db, instance, actor="user-1")
    assert task.id == "task-prepare"
    assert captured["template_code"] == svc.CREATE_SDMS_TEMPLATE_CODE
    assert captured["task_input"] == {"po_no": "POJS2607170008"}


@pytest.mark.asyncio
async def test_ensure_prepare_sub_task_skips_when_task_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _instance(stage=ProcessStage.CREATING_SDMS.value)
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result("task-existing"))
    created = False

    async def _create(*_a, **_k):  # noqa: ANN001
        nonlocal created
        created = True
        return MagicMock()

    monkeypatch.setattr(svc, "_create_sub_task", _create)
    result = await svc._ensure_prepare_sub_task(db, instance, actor="user-1")
    assert result is None
    assert created is False


@pytest.mark.asyncio
async def test_create_from_scan_repairs_stuck_existing_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portal = MagicMock()
    portal.portal_name = "天地伟业-国际-正式演练"
    existing = _instance(stage=ProcessStage.CREATING_SDMS.value, biz_key="POJS2607170008")
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(portal), _scalar_result(existing)])
    db.commit = AsyncMock()
    repaired = False

    async def _ensure(_db, inst, **kwargs):  # noqa: ANN001
        nonlocal repaired
        repaired = True
        assert inst is existing
        assert kwargs["allow_missing_prepare_binding"] is True
        return MagicMock()

    monkeypatch.setattr(svc, "_ensure_prepare_sub_task", _ensure)
    created = await svc.create_from_scan(
        db,
        "tenant-1",
        "portal-1",
        [{"poNo": "POJS2607170008"}],
        actor="user-1",
        allow_missing_prepare_binding=True,
    )
    assert created == []
    assert repaired is True

