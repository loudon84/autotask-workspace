"""京东方发票箱单匹配 / 数量闸门。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError
from app.domain.boe_packing import (
    PROCESS_CODE,
    attachment_rule_errors,
    review_required_errors,
    unmapped_region_codes,
)
from app.models.enums import ProcessInstanceStatus, ProcessStage
from app.models.process_instance import ProcessInstance
from app.models.user_cache import UserCache
from app.services import boe_packing_service as svc
from app.services.boe_packing_service import _header_from_plan, _lines_from_wms, _qty_mismatch, compact_decimal, plan_header_id, qty_is_aligned


def _user() -> UserCache:
    return UserCache(
        user_id="user-1",
        name="客服",
        email="cs@example.com",
        current_org_id="tenant-1",
        org_role="member",
        synced_at=datetime.now(UTC),
    )


def test_qty_mismatch_and_header_mapping() -> None:
    header = _header_from_plan(
        {
            "doc_no": "101SJH2026040195",
            "boe_factory": "1200",
            "deliver_date": "2026-04-17 00:00:00",
            "deliver_qty": 5000,
        },
        matched_at=datetime(2026, 4, 17, 7, 8, 9),
    )
    assert header["invoiceNo"] == "101SJH2026040195"
    assert header["factory"] == "1200"
    assert header["invoiceDate"] == "2026-04-17"
    assert header["consignArrivalDate"] == "2026-04-22"
    assert header["volUnit"] == "立方米"
    assert header["aiRecognize"] is False

    total, lines = _lines_from_wms(
        [
            {
                "cuspo": "9100060074",
                "cusitem": "47-7001373",
                "qty": 100,
                "netweight": "0.45000",
                "cubic": "0.02000000",
                "coo": "TAIWAN,CHINA",
            },
            {
                "cuspo": "9100048919",
                "cusitem": "47-7001645",
                "qty": 4920,
                "netweight": "2.93",
                "cubic": "0.02000000",
                "coo": "TAIWAN,CHINA",
            },
        ]
    )
    assert total == "0.04"
    assert lines[0]["poNum"] == "9100060074"
    assert lines[0]["itemNum"] == "47-7001373"
    assert lines[0]["deliveryQty"] == "100"
    assert lines[0]["netWeight"] == "0.45"
    assert lines[0]["regionCode"] == "TAIWAN,CHINA"
    assert lines[0]["netWeightUnit"] == "千克"
    mismatch, planned, actual = _qty_mismatch(5000, lines)
    assert mismatch is True
    assert planned == "5000"
    assert actual == "5020"
    assert qty_is_aligned({"qtyMismatch": True}) is False
    assert qty_is_aligned({"qtyMismatch": False}) is True


def test_plan_header_id_stays_off_editable_header() -> None:
    row = {
        "doc_no": "101SJH2026040195",
        "header_id": 81543,
        "boe_factory": "1200",
        "deliver_date": "2026-04-17 00:00:00",
    }
    assert plan_header_id(row) == "81543"
    header = _header_from_plan(row, matched_at=datetime(2026, 4, 17, 7, 8, 9))
    assert "headerId" not in header
    assert "header_id" not in header
    instance = ProcessInstance(
        id="inst-id",
        tenant_id="tenant-1",
        process_code=PROCESS_CODE,
        biz_key="101SJH2026040195",
        title="发票箱单",
        portal_account_id="portal-1",
        stage=ProcessStage.BOE_PACK_REVIEW.value,
        status=ProcessInstanceStatus.ACTIVE.value,
        summary=(
            '{"srmDraftNo":"I260908001","headerId":"81543",'
            '"header":{"invoiceNo":"INV-1","factory":"1200"}}'
        ),
        created_by="user-1",
    )
    item = svc.to_list_item(instance)
    assert item["srm_draft_no"] == "I260908001"
    assert item["header_id"] == "81543"
    assert item["latest_task_status"] == ""
    running = svc.to_list_item(instance, latest_task_status="RUNNING")
    assert running["latest_task_status"] == "RUNNING"
    blank = ProcessInstance(
        id="inst-blank",
        tenant_id="tenant-1",
        process_code=PROCESS_CODE,
        biz_key="101SJH1",
        title="发票箱单",
        portal_account_id="portal-1",
        stage=ProcessStage.BOE_PACK_FETCH_WMS.value,
        status=ProcessInstanceStatus.ACTIVE.value,
        summary="{}",
        created_by="user-1",
    )
    empty = svc.to_list_item(blank)
    assert empty["srm_draft_no"] == ""
    assert empty["header_id"] == ""


def test_lines_from_wms_doc_wrapper_shape() -> None:
    """SMC 真实响应是 [{doc_no, total_vol, list: [行...]}]：必须下钻到嵌套 list，
    否则会把外层包装当行、字段全空（2026-09-07 演示库实测踩坑）。"""
    total, lines = _lines_from_wms(
        [
            {
                "doc_no": "101SJH2026040195",
                "total_vol": 0.655,
                "list": [
                    {
                        "doc_no": "101SJH2026040195",
                        "po_num": "9100048919",
                        "item_num": "47-7001645",
                        "delivery_qty": 4920,
                        "net_weight": 2.93,
                        "region": "China_tw",
                    }
                ],
            }
        ]
    )
    assert len(lines) == 1
    assert lines[0]["poNum"] == "9100048919"
    assert lines[0]["itemNum"] == "47-7001645"
    assert lines[0]["deliveryQty"] == "4920"
    assert lines[0]["netWeight"] == "2.93"
    assert lines[0]["regionCode"] == "China_tw"
    assert lines[0]["netWeightUnit"] == "千克"
    assert total == "0.655"


def test_compact_decimal_max_five_places() -> None:
    assert compact_decimal("0.45000") == "0.45"
    assert compact_decimal("3.52100000000000000") == "3.521"
    assert compact_decimal("0.02000000") == "0.02"
    assert compact_decimal("0.06534") == "0.06534"
    assert compact_decimal("") == ""


@pytest.mark.asyncio
async def test_submit_hard_blocks_qty_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = ProcessInstance(
        id="inst-1",
        tenant_id="tenant-1",
        process_code=PROCESS_CODE,
        biz_key="101SJH1",
        title="发票箱单",
        portal_account_id="portal-1",
        stage=ProcessStage.BOE_PACK_REVIEW.value,
        status=ProcessInstanceStatus.ACTIVE.value,
        summary='{"qtyMismatch": true, "qtyWarning": "数量不一致"}',
        created_by="user-1",
    )
    monkeypatch.setattr(svc, "get_packing_instance", AsyncMock(return_value=instance))
    with pytest.raises(BadRequestError) as exc_info:
        await svc.submit_instance(MagicMock(), "tenant-1", "inst-1", _user())
    assert exc_info.value.message_key == "errors.autotask.boe_pack.qty_mismatch"


@pytest.mark.asyncio
async def test_submit_hard_blocks_missing_attachments(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = ProcessInstance(
        id="inst-2",
        tenant_id="tenant-1",
        process_code=PROCESS_CODE,
        biz_key="101SJH202609195",
        title="发票箱单",
        portal_account_id="portal-1",
        stage=ProcessStage.BOE_PACK_REVIEW.value,
        status=ProcessInstanceStatus.ACTIVE.value,
        summary=(
            '{"qtyMismatch": false, "header": {"invoiceNo": "101SJH202609195",'
            '"factory": "1200", "invoiceDate": "2026-09-07", "etd": "2026-09-07",'
            '"consignArrivalDate": "2026-09-12", "totalVol": "0.1"},'
            '"lines": [{"poNum": "9100069442", "deliveryQty": "1",'
            '"netWeight": "1", "regionSrmName": "中国台湾"}]}'
        ),
        created_by="user-1",
    )
    monkeypatch.setattr(svc, "get_packing_instance", AsyncMock(return_value=instance))
    with pytest.raises(BadRequestError) as exc_info:
        await svc.submit_instance(MagicMock(), "tenant-1", "inst-2", _user())
    assert exc_info.value.message_key == "errors.autotask.boe_pack.attachment_invalid"


def test_review_required_and_attachment_rules() -> None:
    header = {
        "invoiceNo": "101SJH202609195",
        "factory": "1200",
        "invoiceDate": "2026-09-07",
        "etd": "2026-09-07",
        "consignArrivalDate": "2026-09-12",
        "totalVol": "0.06",
    }
    lines = [
        {"poNum": "9100069442", "deliveryQty": "10", "netWeight": "1", "regionSrmName": "中国台湾"}
    ]
    assert review_required_errors(header, lines) == []
    assert review_required_errors({**header, "etd": ""}, lines)

    good = [
        {"type": "箱单", "fileName": "PL-101SJH202609195.pdf"},
        {"type": "发票", "fileName": "101SJH202609195.pdf"},
        {"type": "提运单", "fileName": "any.pdf"},
        {"type": "双签PO/协议", "fileName": "9100069442.pdf"},
    ]
    assert attachment_rule_errors(header["invoiceNo"], lines, good) == []
    loose = [
        {"type": "箱单", "fileName": "pl_box.pdf"},
        {"type": "发票", "fileName": "101SJH202609195.pdf"},
        {"type": "双签PO/协议", "fileName": "9100069442.pdf"},
    ]
    assert attachment_rule_errors(header["invoiceNo"], lines, loose) == []
    assert attachment_rule_errors(
        header["invoiceNo"],
        lines,
        [{"type": "箱单", "fileName": "wrong.pdf"}, {"type": "发票", "fileName": "101SJH202609195.pdf"}],
    )


@pytest.mark.asyncio
async def test_enqueue_records_missing_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = ProcessInstance(
        id="inst-bind",
        tenant_id="tenant-1",
        process_code=PROCESS_CODE,
        biz_key="101SJH2",
        title="发票箱单",
        portal_account_id="portal-2",
        stage=ProcessStage.BOE_PACK_ENRICH.value,
        status=ProcessInstanceStatus.ACTIVE.value,
        summary="{}",
        created_by="user-1",
    )
    db = MagicMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)
    monkeypatch.setattr(
        svc,
        "_create_sub_task",
        AsyncMock(
            side_effect=BadRequestError(
                message="未找到模板 srm_boe_pack_enrich 在当前 Portal 的已启用 Binding",
                message_key="errors.autotask.process_binding_missing",
            )
        ),
    )
    task = await svc._maybe_enqueue_rpa(
        db,
        instance,
        template_code="srm_boe_pack_enrich",
        title="补全",
        actor="user-1",
        required=False,
    )
    assert task is None
    assert instance.last_error_code == "PROCESS_BINDING_MISSING"
    assert "未配置对应流程 Binding" in (instance.last_error_message or "")


def test_open_packing_excludes_cancelled() -> None:
    row = ProcessInstance(
        id="c1",
        tenant_id="tenant-1",
        process_code=PROCESS_CODE,
        biz_key="101SJH202609195",
        title="发票箱单",
        portal_account_id="portal-1",
        stage=ProcessStage.BOE_PACK_CANCELLED.value,
        status=ProcessInstanceStatus.CANCELLED.value,
        summary="{}",
        created_by="user-1",
    )
    assert svc._is_open_packing(row) is False
    row.status = ProcessInstanceStatus.ACTIVE.value
    assert svc._is_open_packing(row) is True


@pytest.mark.asyncio
async def test_match_inserts_when_cancelled_does_not_occupy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portal = MagicMock()
    portal.id = "portal-1"
    smc = MagicMock()
    smc.error = None
    smc.data = [
        {
            "doc_no": "101SJH202609195",
            "party_site_number": "C000142-01",
            "org_code": "101",
            "deliver_qty": "1",
            "header_id": "81543",
        }
    ]

    async def _wms(_db, instance, *, actor: str):
        assert actor == "user-1"
        return instance

    monkeypatch.setattr(
        svc.boe_smc_client, "fetch_delivery_plans", AsyncMock(return_value=smc)
    )
    monkeypatch.setattr(svc, "_log_smc", AsyncMock())
    monkeypatch.setattr(svc, "_portal_by_subcode", AsyncMock(return_value=portal))
    monkeypatch.setattr(svc, "_open_instance", AsyncMock(return_value=None))
    monkeypatch.setattr(svc, "fetch_wms_for_instance", AsyncMock(side_effect=_wms))
    db = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    result = await svc.match_delivery_plans(db, "tenant-1", actor="user-1")
    assert result["created_count"] == 1
    db.flush.assert_awaited()
    added = [call.args[0] for call in db.add.call_args_list]
    assert any(isinstance(item, ProcessInstance) for item in added)


def _packing_row(**kwargs) -> ProcessInstance:
    data = dict(
        id="p1",
        tenant_id="tenant-1",
        process_code=PROCESS_CODE,
        biz_key="101SJH1",
        title="发票箱单",
        portal_account_id="portal-1",
        stage=ProcessStage.BOE_PACK_REVIEW.value,
        status=ProcessInstanceStatus.ACTIVE.value,
        summary="{}",
        created_by="user-1",
    )
    data.update(kwargs)
    return ProcessInstance(**data)


@pytest.mark.asyncio
async def test_cancel_without_srm_draft_is_local_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _packing_row(summary="{}")
    monkeypatch.setattr(svc, "get_packing_instance", AsyncMock(return_value=instance))
    monkeypatch.setattr(svc, "_change_stage", MagicMock())
    enqueue = AsyncMock()
    monkeypatch.setattr(svc, "_maybe_enqueue_rpa", enqueue)
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=empty)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    result = await svc.cancel_instance(db, "tenant-1", "p1", _user())
    assert result.status == ProcessInstanceStatus.CANCELLED.value
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_blocked_while_save_draft_inflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _packing_row(summary="{}")
    monkeypatch.setattr(svc, "get_packing_instance", AsyncMock(return_value=instance))
    busy = MagicMock()
    busy.scalar_one_or_none.return_value = "task-1"
    db = MagicMock()
    db.execute = AsyncMock(return_value=busy)
    with pytest.raises(BadRequestError) as exc_info:
        await svc.cancel_instance(db, "tenant-1", "p1", _user())
    assert exc_info.value.message_key == "errors.autotask.boe_pack.cancel_busy"


@pytest.mark.asyncio
async def test_cancel_with_srm_draft_enqueues_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.boe_packing import DELETE_DRAFT_TEMPLATE_CODE

    instance = _packing_row(summary='{"srmDraftNo":"I260910001"}')
    monkeypatch.setattr(svc, "get_packing_instance", AsyncMock(return_value=instance))
    change = MagicMock()
    monkeypatch.setattr(svc, "_change_stage", change)
    enqueue = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(svc, "_maybe_enqueue_rpa", enqueue)
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=empty)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    result = await svc.cancel_instance(db, "tenant-1", "p1", _user())
    assert result.status == ProcessInstanceStatus.ACTIVE.value
    enqueue.assert_awaited()
    assert enqueue.await_args.kwargs["template_code"] == DELETE_DRAFT_TEMPLATE_CODE
    assert change.call_args.args[2] == ProcessStage.BOE_PACK_DELETING_DRAFT


@pytest.mark.asyncio
async def test_dispatch_delete_draft_success_cancels_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.boe_packing import DELETE_DRAFT_TEMPLATE_CODE
    from app.models.enums import RunStatus

    instance = _packing_row(
        stage=ProcessStage.BOE_PACK_DELETING_DRAFT.value,
        summary='{"srmDraftNo":"I260910001"}',
    )
    found = MagicMock()
    found.scalar_one_or_none.return_value = instance
    db = MagicMock()
    db.execute = AsyncMock(return_value=found)
    monkeypatch.setattr(svc, "_change_stage", MagicMock())
    monkeypatch.setattr(svc, "_clear_instance_error", MagicMock())
    task = MagicMock()
    task.task_type = DELETE_DRAFT_TEMPLATE_CODE
    task.process_instance_id = "p1"
    task.created_by = "user-1"
    run = MagicMock()
    run.status = RunStatus.SUCCESS.value
    run.output = {"alreadyMissing": True, "deleted": False}
    run.error_message = None
    handled = await svc.dispatch_finished(db, task, run)
    assert handled is True
    assert instance.status == ProcessInstanceStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_retry_deleting_draft_after_false_failure_searches_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.boe_packing import DELETE_DRAFT_TEMPLATE_CODE

    instance = _packing_row(
        stage=ProcessStage.BOE_PACK_DELETING_DRAFT.value,
        summary='{"srmDraftNo":"I260910102"}',
        last_error_code="BOE_DRAFT_STILL_PRESENT",
        last_error_message="删除后列表仍有流水号 I260910102",
    )
    monkeypatch.setattr(svc, "get_packing_instance", AsyncMock(return_value=instance))
    enqueue = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(svc, "_maybe_enqueue_rpa", enqueue)
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    await svc.retry_instance(db, "tenant-1", "p1", _user())
    enqueue.assert_awaited()
    assert enqueue.await_args.kwargs["template_code"] == DELETE_DRAFT_TEMPLATE_CODE
    assert instance.last_error_code is None
    assert instance.status == ProcessInstanceStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_retry_deleting_draft_busy_does_not_skip_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _packing_row(
        stage=ProcessStage.BOE_PACK_DELETING_DRAFT.value,
        summary='{"srmDraftNo":"I260910102"}',
    )
    monkeypatch.setattr(svc, "get_packing_instance", AsyncMock(return_value=instance))
    monkeypatch.setattr(svc, "_maybe_enqueue_rpa", AsyncMock(return_value=None))
    db = MagicMock()
    with pytest.raises(BadRequestError) as exc_info:
        await svc.retry_instance(db, "tenant-1", "p1", _user())
    assert exc_info.value.message_key == "errors.autotask.boe_pack.retry_busy"


@pytest.mark.asyncio
async def test_dispatch_delete_already_missing_clears_prior_still_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.boe_packing import DELETE_DRAFT_TEMPLATE_CODE
    from app.models.enums import RunStatus

    instance = _packing_row(
        stage=ProcessStage.BOE_PACK_DELETING_DRAFT.value,
        summary='{"srmDraftNo":"I260910102"}',
        last_error_code="BOE_DRAFT_STILL_PRESENT",
        last_error_message="删除后列表仍有流水号 I260910102",
    )
    found = MagicMock()
    found.scalar_one_or_none.return_value = instance
    db = MagicMock()
    db.execute = AsyncMock(return_value=found)
    monkeypatch.setattr(svc, "_change_stage", MagicMock())
    task = MagicMock()
    task.task_type = DELETE_DRAFT_TEMPLATE_CODE
    task.process_instance_id = "p1"
    task.created_by = "user-1"
    run = MagicMock()
    run.status = RunStatus.SUCCESS.value
    run.output = {"alreadyMissing": True, "deleted": False}
    run.error_message = None
    await svc.dispatch_finished(db, task, run)
    assert instance.status == ProcessInstanceStatus.CANCELLED.value
    assert instance.last_error_code is None


def test_unmapped_region_codes_lists_missing_and_empty() -> None:
    assert unmapped_region_codes(
        [{"regionCode": "China_tw"}, {"regionCode": "China_tw"}],
        {"China_tw": "中国台湾"},
    ) == []
    assert unmapped_region_codes(
        [{"regionCode": "NOMAP"}, {"regionCode": ""}],
        {"China_tw": "中国台湾"},
    ) == ["NOMAP", "(空)"]


@pytest.mark.asyncio
async def test_fetch_wms_unmapped_region_stays_and_does_not_enrich(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _packing_row(stage=ProcessStage.BOE_PACK_FETCH_WMS.value)
    wms = MagicMock()
    wms.error = None
    wms.data = [
        {
            "cuspo": "P1",
            "cusitem": "M1",
            "qty": 1,
            "netweight": 1,
            "cubic": 0.1,
            "coo": "NOMAP",
        }
    ]
    wms.url = "http://wms"
    wms.status_code = 200
    monkeypatch.setattr(svc.boe_smc_client, "fetch_wms_packing", AsyncMock(return_value=wms))
    monkeypatch.setattr(svc, "_log_smc", AsyncMock())
    monkeypatch.setattr(
        svc.region_code_map_service, "mapping_dict", AsyncMock(return_value={})
    )
    enqueue = AsyncMock()
    monkeypatch.setattr(svc, "_maybe_enqueue_rpa", enqueue)
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    result = await svc.fetch_wms_for_instance(db, instance, actor="user-1")
    assert result.stage == ProcessStage.BOE_PACK_FETCH_WMS.value
    assert result.last_error_code == "BOE_WMS_REGION_UNMAPPED"
    enqueue.assert_not_awaited()
