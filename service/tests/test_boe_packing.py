"""京东方发票箱单匹配 / 数量闸门。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError
from app.domain.boe_packing import PROCESS_CODE
from app.models.enums import ProcessInstanceStatus, ProcessStage
from app.models.process_instance import ProcessInstance
from app.models.user_cache import UserCache
from app.services import boe_packing_service as svc
from app.domain.boe_packing import attachment_rule_errors, review_required_errors
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
