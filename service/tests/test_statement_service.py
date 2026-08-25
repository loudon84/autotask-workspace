"""statement_service 单测（不连库；mock SDMS / DB）。"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ConflictError
from app.services import statement_service as svc
from app.services.sdms_client import SdmsCheckLookup


def test_receipt_lines_from_summary() -> None:
    assert svc.receipt_lines_from_summary(
        '{"lines":[{"receiptNo":"R1","lineNo":"10"}]}'
    ) == [{"receiptNo": "R1", "lineNo": "10"}]
    assert svc.receipt_lines_from_summary({"lines": [{"receiptNo": "R2"}]}) == [
        {"receiptNo": "R2"}
    ]
    assert svc.receipt_lines_from_summary(None) == []
    assert svc.receipt_lines_from_summary("{}") == []
    assert svc.receipt_lines_from_summary({"lines": "bad"}) == []


def test_sdms_check_num_from_summary() -> None:
    assert svc.sdms_check_num_from_summary('{"sdms_check_num":"104DZ26080001"}') == "104DZ26080001"
    assert svc.sdms_check_num_from_summary({"sdms_check_num": "104DZ26080001"}) == "104DZ26080001"
    assert svc.sdms_check_num_from_summary("{}") is None
    assert svc.sdms_check_num_from_summary(None) is None


def test_sum_line_amounts() -> None:
    total = svc.sum_line_amounts(
        [
            {"taxIncludedAmount": "100.10"},
            {"可立账价税合计（元）": "50.20"},
        ]
    )
    assert total == Decimal("150.30")


def test_sum_line_amounts_empty() -> None:
    with pytest.raises(BadRequestError):
        svc.sum_line_amounts([])


def test_sum_line_amounts_missing_field() -> None:
    with pytest.raises(BadRequestError):
        svc.sum_line_amounts([{"receiptNo": "WR1"}])


def test_build_custom_son_code_joins_customer_and_business_entity() -> None:
    from app.services.sdms_client import build_custom_son_code

    assert build_custom_son_code("C007193-01", "104") == "C007193-01_104"
    assert build_custom_son_code("C007193-01_104", "104") == "C007193-01_104"
    assert build_custom_son_code("C007193-01_104", "") == "C007193-01_104"
    assert build_custom_son_code("", "104") == ""


@pytest.mark.asyncio
async def test_generate_blocks_when_sdms_missing() -> None:
    portal = MagicMock()
    portal.erp_entity_code = "C007193-01"
    portal.ou = "104"
    with (
        patch(
            "app.services.statement_service.sdms_check_url",
            return_value="http://sdms.test/sdms/ar_check/view_doc_srm",
        ),
        patch("app.services.statement_service._get_portal", AsyncMock(return_value=portal)),
        patch(
            "app.services.statement_service.fetch_check_amount",
            AsyncMock(
                return_value=SdmsCheckLookup(
                    None,
                    None,
                    {
                        "create_date_s": "2026-08-01",
                        "create_date_e": "2026-08-31",
                        "custom_son_code": "C007193-01_104",
                    },
                    error="data 为空",
                    url="http://sdms.test/sdms/ar_check/view_doc_srm",
                )
            ),
        ),
    ):
        with pytest.raises(BadRequestError) as exc:
            await svc.generate_statement(
                MagicMock(),
                "t1",
                "pa1",
                [{"taxIncludedAmount": "10.00"}],
                actor="u1",
            )
        assert "未找到" in exc.value.message
        assert "data 为空" in exc.value.message
        assert "view_doc_srm" in exc.value.message


@pytest.mark.asyncio
async def test_generate_blocks_when_amount_mismatch() -> None:
    portal = MagicMock()
    portal.erp_entity_code = "SITE-1"
    portal.ou = "104"
    with (
        patch(
            "app.services.statement_service.sdms_check_url",
            return_value="http://sdms.test/sdms/ar_check/view_doc_srm",
        ),
        patch("app.services.statement_service._get_portal", AsyncMock(return_value=portal)),
        patch(
            "app.services.statement_service.fetch_check_amount",
            AsyncMock(return_value=SdmsCheckLookup(Decimal("20.00"), "36599", {})),
        ),
    ):
        with pytest.raises(ConflictError) as exc:
            await svc.generate_statement(
                MagicMock(),
                "t1",
                "pa1",
                [{"taxIncludedAmount": "10.00"}],
                actor="u1",
            )
        assert "不一致" in exc.value.message
        assert exc.value.message_params["sdms_amount"] == "20.00"
        assert exc.value.message_params["local_amount"] == "10.00"


@pytest.mark.asyncio
async def test_generate_rejects_missing_customer_code() -> None:
    portal = MagicMock()
    portal.erp_entity_code = "  "
    portal.ou = "104"
    with patch("app.services.statement_service._get_portal", AsyncMock(return_value=portal)):
        with pytest.raises(BadRequestError) as exc:
            await svc.generate_statement(
                MagicMock(),
                "t1",
                "pa1",
                [{"taxIncludedAmount": "10.00"}],
                actor="u1",
            )
    assert "编号" in exc.value.message


@pytest.mark.asyncio
async def test_generate_rejects_missing_business_entity_code() -> None:
    portal = MagicMock()
    portal.erp_entity_code = "C007193-01"
    portal.ou = ""
    with patch("app.services.statement_service._get_portal", AsyncMock(return_value=portal)):
        with pytest.raises(BadRequestError) as exc:
            await svc.generate_statement(
                MagicMock(),
                "t1",
                "pa1",
                [{"taxIncludedAmount": "10.00"}],
                actor="u1",
            )
    assert "我方公司编号" in exc.value.message


@pytest.mark.asyncio
async def test_generate_rejects_missing_sdms_base_url() -> None:
    portal = MagicMock()
    portal.erp_entity_code = "SITE-1"
    portal.ou = "104"
    with (
        patch("app.services.statement_service._get_portal", AsyncMock(return_value=portal)),
        patch("app.services.statement_service.sdms_check_url", return_value=""),
    ):
        with pytest.raises(BadRequestError) as exc:
            await svc.generate_statement(
                MagicMock(),
                "t1",
                "pa1",
                [{"taxIncludedAmount": "10.00"}],
                actor="u1",
            )
    assert "SMC_API_BASE_URL" in exc.value.message


def _empty_execute() -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    return result


def _assign_ids_on_flush(db: MagicMock) -> None:
    import uuid

    async def _flush() -> None:
        for call in db.add.call_args_list:
            obj = call.args[0]
            if getattr(obj, "id", None) in (None,):
                obj.id = str(uuid.uuid4())

    db.flush = AsyncMock(side_effect=_flush)


@pytest.mark.asyncio
async def test_generate_ok_creates_draft_bill_and_task() -> None:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_execute())
    _assign_ids_on_flush(db)

    portal = MagicMock()
    portal.entity_type = "CUSTOMER"
    portal.erp_entity_code = "C1"
    portal.erp_entity_name = "客户"
    portal.ou = "104"
    binding = MagicMock()
    binding.id = "b1"
    binding.rpa_flow_id = "rpa_flow_srm_stmt_generate"

    fetch_mock = AsyncMock(
        return_value=SdmsCheckLookup(Decimal("10.00"), "36599", {}, check_num="104DZ26080001")
    )
    with (
        patch(
            "app.services.statement_service.fetch_check_amount",
            fetch_mock,
        ),
        patch(
            "app.services.statement_service.sdms_check_url",
            return_value="http://sdms.test/sdms/ar_check/view_doc_srm",
        ),
        patch("app.services.statement_service._get_portal", AsyncMock(return_value=portal)),
        patch("app.services.statement_service._find_binding", AsyncMock(return_value=binding)),
    ):
        result = await svc.generate_statement(
            db,
            "t1",
            "pa1",
            [{"taxIncludedAmount": "10.00", "receiptNo": "WR1", "lineNo": "10"}],
            actor="u1",
            date_start="2026-08-01",
            date_end="2026-08-31",
            today=date(2026, 8, 17),
        )

    assert result["ok"] is True
    assert result["local_amount"] == "10.00"
    assert result["sdms_amount"] == "10.00"
    assert result["sdms_check_head_id"] == "36599"
    fetch_mock.assert_awaited_once()
    assert fetch_mock.await_args.kwargs["customer_site"] == "C1_104"
    assert result["sdms_check_num"] == "104DZ26080001"
    assert result["bill_id"]
    added_bills = [call.args[0] for call in db.add.call_args_list if call.args[0].__class__.__name__ == "StatementBill"]
    assert added_bills[0].check_status == "DRAFT"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_generate_reuses_existing_draft() -> None:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    _assign_ids_on_flush(db)

    bill = MagicMock()
    bill.id = "bill-draft"
    bill.check_status = "DRAFT"
    bill.process_instance_id = "inst-1"
    bill.last_error = "上次失败"
    instance = MagicMock()
    instance.id = "inst-1"
    execute_bill = MagicMock()
    execute_bill.scalar_one_or_none.return_value = bill
    execute_instance = MagicMock()
    execute_instance.scalar_one.return_value = instance
    db.execute = AsyncMock(side_effect=[execute_bill, execute_instance])

    task = MagicMock()
    task.id = "task-retry"
    portal = MagicMock()
    portal.erp_entity_code = "C007193-01"
    portal.ou = "104"
    with (
        patch(
            "app.services.statement_service.fetch_check_amount",
            AsyncMock(return_value=SdmsCheckLookup(Decimal("10.00"), "36599", {})),
        ),
        patch(
            "app.services.statement_service.sdms_check_url",
            return_value="http://sdms.test/sdms/ar_check/view_doc_srm",
        ),
        patch("app.services.statement_service._get_portal", AsyncMock(return_value=portal)),
        patch("app.services.statement_service._create_standalone_task", AsyncMock(return_value=task)),
    ):
        result = await svc.generate_statement(
            db,
            "t1",
            "pa1",
            [{"taxIncludedAmount": "10.00"}],
            actor="u1",
            today=date(2026, 8, 17),
        )

    assert result["bill_id"] == "bill-draft"
    assert bill.last_error is None
    assert instance.stage == "STMT_GENERATING"


@pytest.mark.asyncio
async def test_generate_rejects_duplicate_non_draft() -> None:
    db = MagicMock()
    existing = MagicMock()
    existing.check_status = "UNCHECKED"
    execute_bill = MagicMock()
    execute_bill.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=execute_bill)
    portal = MagicMock()
    portal.erp_entity_code = "C007193-01"
    portal.ou = "104"
    with (
        patch(
            "app.services.statement_service.fetch_check_amount",
            AsyncMock(return_value=SdmsCheckLookup(Decimal("10.00"), "36599", {})),
        ),
        patch(
            "app.services.statement_service.sdms_check_url",
            return_value="http://sdms.test/sdms/ar_check/view_doc_srm",
        ),
        patch("app.services.statement_service._get_portal", AsyncMock(return_value=portal)),
    ):
        with pytest.raises(ConflictError) as exc:
            await svc.generate_statement(
                db,
                "t1",
                "pa1",
                [{"taxIncludedAmount": "10.00"}],
                actor="u1",
                today=date(2026, 8, 17),
            )
    assert "已存在" in exc.value.message


@pytest.mark.asyncio
async def test_on_generate_finished_success_promotes_draft() -> None:
    instance = MagicMock()
    instance.tenant_id = "t1"
    instance.portal_account_id = "pa1"
    instance.summary = '{"sdms_check_head_id":"36599"}'
    instance.status = "ACTIVE"
    bill = MagicMock()
    bill.check_status = "DRAFT"
    bill.last_error = "old"
    task = MagicMock()
    task.process_instance_id = "inst-1"
    task.created_by = "u1"
    run = MagicMock()
    run.status = "SUCCESS"
    run.output = {"checkDate": "2026-04-30", "checkAmount": "10.00"}
    db = MagicMock()
    exec_instance = MagicMock()
    exec_instance.scalar_one_or_none.return_value = instance
    exec_bill = MagicMock()
    exec_bill.scalar_one_or_none.return_value = bill
    db.execute = AsyncMock(side_effect=[exec_instance, exec_bill])
    with patch("app.services.statement_service.process_svc._change_stage") as change_stage:
        await svc.on_generate_finished(db, task, run)
    assert bill.check_status == "UNCHECKED"
    assert bill.last_error is None
    assert instance.status == "ACTIVE"
    change_stage.assert_called_once()


@pytest.mark.asyncio
async def test_on_generate_finished_dry_run_keeps_draft() -> None:
    instance = MagicMock()
    instance.summary = '{"sdms_check_head_id":"36599"}'
    instance.status = "ACTIVE"
    instance.last_error_code = "old"
    bill = MagicMock()
    bill.check_status = "DRAFT"
    bill.last_error = "old"
    task = MagicMock()
    task.process_instance_id = "inst-1"
    run = MagicMock()
    run.status = "SUCCESS"
    run.output = {
        "checkDate": "2026-08-21",
        "checkAmount": "10.00",
        "committed": False,
        "dryRun": True,
        "blockedAction": "generate_statement",
        "generateButtonFound": True,
    }
    db = MagicMock()
    exec_instance = MagicMock()
    exec_instance.scalar_one_or_none.return_value = instance
    exec_bill = MagicMock()
    exec_bill.scalar_one_or_none.return_value = bill
    db.execute = AsyncMock(side_effect=[exec_instance, exec_bill])
    with patch("app.services.statement_service.process_svc._change_stage") as change_stage:
        await svc.on_generate_finished(db, task, run)
    assert bill.check_status == "DRAFT"
    assert bill.last_error is None
    assert instance.status == "ACTIVE"
    change_stage.assert_not_called()


@pytest.mark.asyncio
async def test_on_generate_finished_failure_keeps_draft_active() -> None:
    instance = MagicMock()
    instance.status = "ACTIVE"
    bill = MagicMock()
    bill.check_status = "DRAFT"
    task = MagicMock()
    task.process_instance_id = "inst-1"
    run = MagicMock()
    run.status = "FAILED"
    run.error_code = "FLOW_ERROR"
    run.error_message = "SRM 生成失败"
    db = MagicMock()
    exec_instance = MagicMock()
    exec_instance.scalar_one_or_none.return_value = instance
    exec_bill = MagicMock()
    exec_bill.scalar_one_or_none.return_value = bill
    db.execute = AsyncMock(side_effect=[exec_instance, exec_bill])
    await svc.on_generate_finished(db, task, run)
    assert instance.status == "ACTIVE"
    assert bill.check_status == "DRAFT"
    assert bill.last_error == "SRM 生成失败"


def test_parse_optional_money_accepts_ocr_noise() -> None:
    assert svc.parse_optional_money("") is None
    assert svc.parse_optional_money("  ") is None
    assert svc.parse_optional_money("未上传") is None
    assert svc.parse_optional_money("—") is None
    assert svc.parse_optional_money("¥1,151,309.12") == Decimal("1151309.12")
    assert svc.parse_optional_money("1151309.12元 已上传") == Decimal("1151309.12")


@pytest.mark.asyncio
async def test_on_upload_finished_writes_invoice_keeps_unchecked() -> None:
    from app.services.json_utils import dumps_json, loads_json

    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    bill.invoice_status = "NOT_UPLOADED"
    bill.last_error = None
    instance = MagicMock()
    instance.summary = "{}"
    instance.status = "ACTIVE"
    task = MagicMock()
    task.input = dumps_json({"billId": "bill-1", "filePaths": [r"C:\invoices\a.pdf"]})
    task.process_instance_id = "inst-1"
    run = MagicMock()
    run.status = "SUCCESS"
    run.output = {"invoiceNo": "INV001", "invoiceAmount": "10.00"}
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(bill), _scalar_result(instance)])
    with patch("app.services.statement_service.process_svc._change_stage") as change_stage:
        await svc.on_upload_finished(db, task, run)
    assert bill.invoice_no == "INV001"
    assert bill.invoice_amount == Decimal("10.00")
    assert bill.invoice_status == "UPLOADED"
    assert bill.check_status == "UNCHECKED"
    assert bill.last_error is None
    change_stage.assert_not_called()
    summary = loads_json(instance.summary, {})
    assert summary["invoice_scan"]["invoiceNo"] == "INV001"


@pytest.mark.asyncio
async def test_upload_invoice_queues_scan_task() -> None:
    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    bill.process_instance_id = "inst-1"
    bill.portal_account_id = "pa1"
    bill.check_date = date(2026, 4, 1)
    bill.check_amount = Decimal("10.00")
    bill.id = "bill-1"
    task = MagicMock()
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    with (
        patch("app.services.statement_service.get_bill", AsyncMock(return_value=bill)),
        patch(
            "app.services.statement_service._create_standalone_task",
            AsyncMock(return_value=task),
        ) as create_task,
    ):
        result = await svc.upload_invoice(
            db, "t1", "bill-1", file_paths=["a.pdf"], actor="u1"
        )
    assert result is task
    assert create_task.await_args.kwargs["template_code"] == "srm_stmt_upload_invoice"


@pytest.mark.asyncio
async def test_upload_invoice_rejects_draft() -> None:
    bill = MagicMock()
    bill.check_status = "DRAFT"
    with patch("app.services.statement_service.get_bill", AsyncMock(return_value=bill)):
        with pytest.raises(BadRequestError) as exc:
            await svc.upload_invoice(MagicMock(), "t1", "bill-1", file_paths=["a.pdf"], actor="u1")
        assert "待生成" in exc.value.message


@pytest.mark.asyncio
async def test_retry_generate_draft_only() -> None:
    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    with patch("app.services.statement_service.get_bill", AsyncMock(return_value=bill)):
        with pytest.raises(BadRequestError) as exc:
            await svc.retry_generate(MagicMock(), "t1", "bill-1", actor="u1")
        assert "待生成" in exc.value.message


@pytest.mark.asyncio
async def test_submit_review_requires_prior_scan() -> None:
    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    bill.invoice_no = None
    bill.invoice_amount = None
    with patch("app.services.statement_service.get_bill", AsyncMock(return_value=bill)):
        with pytest.raises(BadRequestError) as exc:
            await svc.submit_review(MagicMock(), "t1", "bill-1", file_paths=["a.pdf"], actor="u1")
        assert "扫描发票" in exc.value.message


@pytest.mark.asyncio
async def test_submit_review_requires_files() -> None:
    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    bill.invoice_no = "INV1"
    bill.invoice_amount = Decimal("10.00")
    with patch("app.services.statement_service.get_bill", AsyncMock(return_value=bill)):
        with pytest.raises(BadRequestError) as exc:
            await svc.submit_review(MagicMock(), "t1", "bill-1", file_paths=[], actor="u1")
        assert "发票文件" in exc.value.message


@pytest.mark.asyncio
async def test_submit_review_rejects_changed_files() -> None:
    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    bill.invoice_no = "INV1"
    bill.invoice_amount = Decimal("10.00")
    bill.process_instance_id = "inst-1"
    instance = MagicMock()
    instance.summary = '{"invoice_scan":{"filePaths":["C:\\\\invoices\\\\a.pdf"]}}'
    with (
        patch("app.services.statement_service.get_bill", AsyncMock(return_value=bill)),
        patch("app.services.statement_service.get_bill_instance", AsyncMock(return_value=instance)),
    ):
        with pytest.raises(BadRequestError) as exc:
            await svc.submit_review(
                MagicMock(), "t1", "bill-1", file_paths=["C:\\invoices\\b.pdf"], actor="u1"
            )
        assert "重新扫描" in exc.value.message


@pytest.mark.asyncio
async def test_cancel_statement_local_only() -> None:
    bill = MagicMock()
    bill.id = "bill-1"
    bill.check_status = "UNCHECKED"
    bill.process_instance_id = "inst-1"
    bill.last_error = "old"

    instance = MagicMock()
    instance.id = "inst-1"
    instance.stage = "STMT_PENDING_INVOICE"

    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=instance)))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch("app.services.statement_service.get_bill", AsyncMock(return_value=bill)),
        patch("app.services.statement_service.process_svc._change_stage") as change_stage,
    ):
        result = await svc.cancel_statement(db, "t1", "bill-1", actor="u1")

    assert result.check_status == "VOID"
    change_stage.assert_called_once()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_fetch_check_amount_parses_payload() -> None:
    from app.services import sdms_client

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "code": 1,
        "data": [{"check_head_id": 36599, "check_num": "104DZ26080001", "check_amount": 20739830.66}],
    }
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.sdms_client.httpx.AsyncClient", return_value=mock_client) as client_cls:
        lookup = await sdms_client.fetch_check_amount(
            date(2026, 8, 17),
            url="http://sdms.test/sdms/ar_check/view_doc_srm",
            customer_site="C007193-01_104",
        )

    assert lookup.amount == Decimal("20739830.66")
    assert lookup.check_head_id == "36599"
    assert lookup.check_num == "104DZ26080001"
    assert client_cls.call_args.kwargs.get("trust_env") is False
    params = mock_client.get.await_args.kwargs["params"]
    assert params["custom_son_code"] == "C007193-01_104"
    assert mock_client.get.await_args.args[0] == "http://sdms.test/sdms/ar_check/view_doc_srm"
    assert params["create_date_s"] == "2026-08-01"
    assert params["create_date_e"] == "2026-08-31"


@pytest.mark.asyncio
async def test_fetch_check_amount_keeps_sdms_error() -> None:
    from app.services import sdms_client

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 0, "msg": "ORA-01830: date format"}
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.sdms_client.httpx.AsyncClient", return_value=mock_client):
        lookup = await sdms_client.fetch_check_amount(
            date(2026, 8, 17),
            url="http://sdms.test/sdms/ar_check/view_doc_srm",
            customer_site="SITE-1",
        )

    assert lookup.amount is None
    assert "ORA-01830" in (lookup.error or "")


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_on_submit_finished_uploads_sdms_after_srm_success() -> None:
    from app.services.json_utils import dumps_json

    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    bill.last_error = None
    instance = MagicMock()
    instance.summary = dumps_json({"sdms_check_num": "104DZ26080001"})
    task = MagicMock()
    task.process_instance_id = "inst-1"
    task.input = dumps_json(
        {
            "billId": "bill-1",
            "filePaths": [r"C:\invoices\a.pdf"],
            "sdmsCheckNum": "104DZ26080001",
            "sdmsUsername": "S01",
        }
    )
    run = MagicMock()
    run.status = "SUCCESS"
    run.output = {"invoiceNo": "INV1", "invoiceAmount": "10.00"}
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(bill), _scalar_result(instance)])

    with (
        patch("app.services.statement_service.process_svc._change_stage") as change_stage,
        patch(
            "app.services.statement_service.upload_statement_invoices_to_sdms",
            AsyncMock(return_value=None),
        ) as upload,
    ):
        await svc.on_submit_finished(db, task, run)

    assert bill.check_status == "CHECKED"
    assert bill.invoice_status == "REVIEWING"
    assert bill.last_error is None
    change_stage.assert_called_once()
    upload.assert_awaited_once()
    assert upload.await_args.kwargs["check_num"] == "104DZ26080001"
    assert upload.await_args.kwargs["username"] == "S01"


@pytest.mark.asyncio
async def test_on_submit_finished_keeps_submitted_when_sdms_attach_fails() -> None:
    from app.services.json_utils import dumps_json

    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    instance = MagicMock()
    instance.summary = "{}"
    task = MagicMock()
    task.process_instance_id = "inst-1"
    task.input = dumps_json(
        {
            "billId": "bill-1",
            "filePaths": [r"C:\invoices\a.pdf"],
            "sdmsCheckNum": "104DZ26080001",
            "sdmsUsername": "S01",
        }
    )
    run = MagicMock()
    run.status = "SUCCESS"
    run.output = {"invoiceNo": "INV1", "invoiceAmount": "10.00"}
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(bill), _scalar_result(instance)])

    with (
        patch("app.services.statement_service.process_svc._change_stage"),
        patch(
            "app.services.statement_service.upload_statement_invoices_to_sdms",
            AsyncMock(return_value="SRM 已提交，发票传到 SDMS 失败：HTTP 500"),
        ),
    ):
        await svc.on_submit_finished(db, task, run)

    assert bill.check_status == "CHECKED"
    assert instance.status == "COMPLETED"
    assert "SDMS" in (bill.last_error or "")


@pytest.mark.asyncio
async def test_on_submit_finished_dry_run_keeps_unchecked() -> None:
    from app.services.json_utils import dumps_json

    bill = MagicMock()
    bill.check_status = "UNCHECKED"
    bill.invoice_status = "NOT_UPLOADED"
    bill.last_error = "old"
    instance = MagicMock()
    instance.summary = dumps_json({"drill": {"shadow": True}})
    instance.status = "ACTIVE"
    instance.last_error_code = "old"
    task = MagicMock()
    task.process_instance_id = "inst-1"
    task.input = dumps_json({"billId": "bill-1", "filePaths": [r"C:\invoices\a.pdf"]})
    run = MagicMock()
    run.status = "SUCCESS"
    run.output = {
        "invoiceNo": "INV1",
        "invoiceAmount": "10.00",
        "committed": False,
        "dryRun": True,
        "blockedAction": "submit_review",
        "submitButtonFound": True,
    }
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(bill), _scalar_result(instance)])

    with (
        patch("app.services.statement_service.process_svc._change_stage") as change_stage,
        patch(
            "app.services.statement_service.upload_statement_invoices_to_sdms",
            AsyncMock(return_value=None),
        ) as upload,
    ):
        await svc.on_submit_finished(db, task, run)

    assert bill.check_status == "UNCHECKED"
    assert bill.invoice_status == "NOT_UPLOADED"
    assert bill.last_error is None
    assert instance.status == "ACTIVE"
    change_stage.assert_not_called()
    upload.assert_not_awaited()
