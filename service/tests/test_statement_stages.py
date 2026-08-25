"""天地伟业对账单流程：阶段枚举与 STAGE_DEFINITIONS。"""

from app.models.enums import ProcessStage, ProcessSubTaskKind
from app.services import process_instance_service as svc


def test_statement_stages_exist_in_enum() -> None:
    assert ProcessStage.STMT_GENERATING.value == "STMT_GENERATING"
    assert ProcessStage.STMT_PENDING_INVOICE.value == "STMT_PENDING_INVOICE"
    assert ProcessStage.STMT_PENDING_REVIEW.value == "STMT_PENDING_REVIEW"
    assert ProcessStage.STMT_SUBMITTED.value == "STMT_SUBMITTED"
    assert ProcessStage.STMT_CANCELLED.value == "STMT_CANCELLED"


def test_statement_sub_task_kinds_exist() -> None:
    assert ProcessSubTaskKind.STMT_QUERY_RECEIPTS.value == "STMT_QUERY_RECEIPTS"
    assert ProcessSubTaskKind.STMT_GENERATE.value == "STMT_GENERATE"
    assert ProcessSubTaskKind.STMT_UPLOAD_INVOICE.value == "STMT_UPLOAD_INVOICE"
    assert ProcessSubTaskKind.STMT_SUBMIT_REVIEW.value == "STMT_SUBMIT_REVIEW"


def test_tiandi_statement_stage_definitions() -> None:
    stages = svc.stage_definitions_for(svc.PROCESS_CODE_SRM_TIANDI_STATEMENT)
    assert [item["id"] for item in stages] == [
        "STMT_GENERATING",
        "STMT_PENDING_INVOICE",
        "STMT_PENDING_REVIEW",
        "STMT_SUBMITTED",
        "STMT_CANCELLED",
    ]
    by_id = {item["id"]: item for item in stages}
    assert by_id["STMT_GENERATING"]["button"] == "重新生成"
    assert by_id["STMT_PENDING_INVOICE"]["button"] == "提交审核"
    assert by_id["STMT_PENDING_REVIEW"]["name"] == "提交审核"
    assert by_id["STMT_PENDING_REVIEW"]["button"] == "提交审核"
    assert by_id["STMT_SUBMITTED"]["button"] is None
    assert by_id["STMT_CANCELLED"]["button"] is None


def test_customer_order_stage_definitions_unchanged() -> None:
    stages = svc.stage_definitions_for(svc.PROCESS_CODE_SRM_CUSTOMER_ORDER)
    assert stages[0]["id"] == "CREATING_SDMS"
    assert stages[-1]["id"] == "FAILED"


def test_statement_template_codes() -> None:
    assert svc.STMT_QUERY_RECEIPTS_TEMPLATE_CODE == "srm_stmt_query_receipts"
    assert svc.STMT_GENERATE_TEMPLATE_CODE == "srm_stmt_generate"
    assert svc.STMT_UPLOAD_INVOICE_TEMPLATE_CODE == "srm_stmt_upload_invoice"
    assert svc.STMT_SUBMIT_REVIEW_TEMPLATE_CODE == "srm_stmt_submit_review"
