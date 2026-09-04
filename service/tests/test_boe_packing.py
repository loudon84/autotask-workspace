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
from app.services.boe_packing_service import _header_from_plan, _lines_from_wms, _qty_mismatch, qty_is_aligned


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
    assert lines[0]["netWeight"] == "0.45000"
    assert lines[0]["regionCode"] == "TAIWAN,CHINA"
    mismatch, planned, actual = _qty_mismatch(5000, lines)
    assert mismatch is True
    assert planned == "5000"
    assert actual == "5020"
    assert qty_is_aligned({"qtyMismatch": True}) is False
    assert qty_is_aligned({"qtyMismatch": False}) is True


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
