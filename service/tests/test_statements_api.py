"""statements API schemas 契约测试（不加载 FastAPI 路由，避免依赖鉴权包）。"""

from datetime import date, datetime
from decimal import Decimal

from app.schemas.statement import (
    StatementBillDetail,
    StatementBillListItem,
    StatementGenerateRequest,
    StatementGenerateResponse,
    StatementQueryReceiptsRequest,
)


def test_generate_request_accepts_camel_case() -> None:
    body = StatementGenerateRequest.model_validate(
        {
            "portalAccountId": "pa-1",
            "lines": [{"taxIncludedAmount": "1.00"}],
            "dateStart": "2026-08-01",
            "dateEnd": "2026-08-31",
        }
    )
    assert body.portal_account_id == "pa-1"
    assert body.date_start == "2026-08-01"


def test_query_request_accepts_snake_case() -> None:
    body = StatementQueryReceiptsRequest.model_validate(
        {
            "portal_account_id": "pa-1",
            "date_start": "2026-08-01",
            "date_end": "2026-08-31",
        }
    )
    assert body.portal_account_id == "pa-1"


def test_generate_response_alias() -> None:
    payload = StatementGenerateResponse(
        ok=True,
        instance_id="i1",
        task_id="t1",
        bill_id="bill-1",
        local_amount="10.00",
        sdms_amount="10.00",
        sdms_check_head_id="36599",
    ).model_dump(by_alias=True)
    assert payload["instanceId"] == "i1"
    assert payload["taskId"] == "t1"
    assert payload["billId"] == "bill-1"
    assert payload["localAmount"] == "10.00"


def test_list_item_sop_aliases() -> None:
    payload = StatementBillListItem(
        id="b1",
        process_instance_id="i1",
        portal_account_id="p1",
        check_date=date(2026, 8, 17),
        check_amount=Decimal("10.00"),
        check_status="DRAFT",
        invoice_status="NOT_UPLOADED",
        created_at=datetime(2026, 8, 18, 3, 0, 0),
        updated_at=datetime(2026, 8, 18, 3, 0, 0),
        stage="STMT_GENERATING",
        instance_status="ACTIVE",
        last_error_code="FLOW_ERROR",
    ).model_dump(by_alias=True)
    assert payload["stage"] == "STMT_GENERATING"
    assert payload["instanceStatus"] == "ACTIVE"
    assert payload["lastErrorCode"] == "FLOW_ERROR"


def test_detail_includes_stage_history_alias() -> None:
    payload = StatementBillDetail(
        id="b1",
        process_instance_id="i1",
        portal_account_id="p1",
        check_date=date(2026, 8, 17),
        check_amount=Decimal("10.00"),
        check_status="UNCHECKED",
        invoice_status="NOT_UPLOADED",
        created_at=datetime(2026, 8, 18, 3, 0, 0),
        updated_at=datetime(2026, 8, 18, 3, 0, 0),
        stage="STMT_PENDING_INVOICE",
        instance_status="ACTIVE",
        stage_history=[],
        sub_tasks=[],
        lines=[{"receiptNo": "R1", "lineNo": "10"}],
    ).model_dump(by_alias=True)
    assert payload["stage"] == "STMT_PENDING_INVOICE"
    assert payload["stageHistory"] == []
    assert payload["subTasks"] == []
    assert payload["lines"][0]["receiptNo"] == "R1"
