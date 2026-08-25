"""天地伟业对账单业务编排。

对应 project-docs/prd/AutoTask v3.0 业务需求-天地伟业对账单.md：
- 生成前 SDMS 金额校验（无容差）
- 校验通过即落 DRAFT（待生成草稿）；SRM 成功后改为未对账
- 取消对账仅本地作废
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import (
    ProcessInstanceStatus,
    ProcessStage,
    RunStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.models.rpa_run import RpaRun
from app.models.statement_bill import StatementBill
from app.models.workflow_binding import WorkflowBinding
from app.schemas.process import ProcessStageHistoryResponse, ProcessSubTaskResponse
from app.schemas.statement import StatementBillDetail, StatementBillListItem
from app.services import process_instance_service as process_svc
from app.services.json_utils import dumps_json, loads_json
from app.services.runtime_endpoints import sdms_check_url
from app.services.sdms_attachment_client import upload_statement_invoices_to_sdms
from app.services.sdms_client import build_custom_son_code, describe_lookup, fetch_check_amount

PROCESS_CODE = process_svc.PROCESS_CODE_SRM_TIANDI_STATEMENT

AMOUNT_KEYS = (
    "taxIncludedAmount",
    "tax_included_amount",
    "可立账价税合计（元）",
    "可立账价税合计",
    "价税合计",
)


def _line_amount(line: dict) -> Decimal:
    for key in AMOUNT_KEYS:
        if key in line and line[key] is not None and str(line[key]).strip() != "":
            try:
                return Decimal(str(line[key]).replace(",", "").strip())
            except (InvalidOperation, ValueError) as exc:
                raise BadRequestError(
                    message=f"行金额格式错误: {line.get(key)}",
                    message_key="errors.autotask.statement.invalid_line_amount",
                ) from exc
    raise BadRequestError(
        message="勾选行缺少可立账价税合计",
        message_key="errors.autotask.statement.line_amount_missing",
    )


def sum_line_amounts(lines: list[dict]) -> Decimal:
    if not lines:
        raise BadRequestError(
            message="请至少勾选一行收货明细",
            message_key="errors.autotask.statement.lines_empty",
        )
    total = Decimal("0.00")
    for line in lines:
        if not isinstance(line, dict):
            raise BadRequestError(
                message="勾选行格式错误",
                message_key="errors.autotask.statement.line_invalid",
            )
        total += _line_amount(line)
    return total.quantize(Decimal("0.01"))


async def _find_binding(
    db: AsyncSession,
    tenant_id: str,
    portal_account_id: str,
    template_code: str,
) -> WorkflowBinding:
    return await process_svc._find_binding(db, tenant_id, portal_account_id, template_code)


async def _get_portal(db: AsyncSession, portal_account_id: str) -> PortalAccount:
    portal = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == portal_account_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if portal is None:
        raise NotFoundError(message="Portal 账号不存在", message_key="errors.autotask.portal_not_found")
    return portal


async def _create_standalone_task(
    db: AsyncSession,
    *,
    tenant_id: str,
    portal_account_id: str,
    template_code: str,
    title: str,
    task_input: dict,
    actor: str,
    process_instance_id: str | None = None,
) -> AutomationTask:
    portal = await _get_portal(db, portal_account_id)
    binding = await _find_binding(db, tenant_id, portal_account_id, template_code)
    task = AutomationTask(
        tenant_id=tenant_id,
        title=title,
        task_type=template_code,
        portal_account_id=portal_account_id,
        workflow_binding_id=binding.id,
        entity_type=portal.entity_type,
        erp_entity_code=portal.erp_entity_code,
        erp_entity_name=portal.erp_entity_name,
        status=TaskStatus.QUEUED,
        priority=TaskPriority.NORMAL,
        input=dumps_json(task_input),
        created_by=actor,
        assigned_to=actor,
        process_instance_id=process_instance_id,
    )
    db.add(task)
    await db.flush()
    db.add(
        RpaRun(
            task_id=task.id,
            rpa_flow_id=binding.rpa_flow_id,
            status=RunStatus.QUEUED,
        )
    )
    return task


async def query_receipts(
    db: AsyncSession,
    tenant_id: str,
    portal_account_id: str,
    date_start: str,
    date_end: str,
    *,
    actor: str,
) -> AutomationTask:
    """创建收货列表查询子任务（临时任务，不落 statement_bills）。"""
    if not date_start or not date_end:
        raise BadRequestError(
            message="请填写入库确认时间起止",
            message_key="errors.autotask.statement.date_range_required",
        )
    task = await _create_standalone_task(
        db,
        tenant_id=tenant_id,
        portal_account_id=portal_account_id,
        template_code=process_svc.STMT_QUERY_RECEIPTS_TEMPLATE_CODE,
        title="对账单：查询收货列表",
        task_input={"dateStart": date_start, "dateEnd": date_end},
        actor=actor,
    )
    await db.commit()
    await db.refresh(task)
    return task


async def generate_statement(
    db: AsyncSession,
    tenant_id: str,
    portal_account_id: str,
    lines: list[dict],
    *,
    actor: str,
    date_start: str | None = None,
    date_end: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """校验 SDMS 金额后创建流程实例 + 生成对账单子任务。"""
    local_amount = sum_line_amounts(lines)
    portal = await _get_portal(db, portal_account_id)
    customer_code = (portal.erp_entity_code or "").strip()
    business_entity_code = (getattr(portal, "ou", None) or "").strip()
    if not customer_code:
        raise BadRequestError(
            message="门户缺少客户/供应商编号",
            message_key="errors.autotask.statement.customer_code_missing",
        )
    if not business_entity_code and "_" not in customer_code:
        raise BadRequestError(
            message="门户缺少我方公司编号",
            message_key="errors.autotask.statement.business_entity_code_missing",
        )
    custom_son_code = build_custom_son_code(customer_code, business_entity_code)
    check_url = sdms_check_url()
    if not check_url:
        raise BadRequestError(
            message="未配置 SMC_API_BASE_URL，无法查询对账单",
            message_key="errors.autotask.statement.sdms_url_missing",
        )
    lookup = await fetch_check_amount(today, url=check_url, customer_site=custom_son_code)
    sdms_amount, check_head_id, check_num = (
        lookup.amount,
        lookup.check_head_id,
        lookup.check_num,
    )
    if sdms_amount is None:
        raise BadRequestError(
            message=(
                f"未找到 SDMS 对账单，请自行匹配后重试。"
                f" 原因：{lookup.error or '未知'}。"
                f" {describe_lookup(lookup)}"
            ),
            message_key="errors.autotask.statement.sdms_not_found",
            message_params={
                "reason": lookup.error or "",
                "request": describe_lookup(lookup),
            },
        )
    if sdms_amount != local_amount:
        raise ConflictError(
            message=(
                f"对账金额不一致：SDMS {sdms_amount} vs 勾选汇总 {local_amount}，"
                "请去 SDMS 修改对账单后重新发起"
            ),
            message_key="errors.autotask.statement.amount_mismatch",
            message_params={
                "sdms_amount": str(sdms_amount),
                "local_amount": str(local_amount),
            },
        )

    check_date = today or date.today()
    existing = (
        await db.execute(
            select(StatementBill).where(
                StatementBill.tenant_id == tenant_id,
                StatementBill.check_date == check_date,
                StatementBill.check_amount == local_amount,
                not_deleted(StatementBill),
            )
        )
    ).scalar_one_or_none()

    summary = {
        "local_amount": str(local_amount),
        "sdms_check_head_id": check_head_id,
        "sdms_check_num": check_num,
        "date_start": date_start,
        "date_end": date_end,
        "lines": lines,
    }

    if existing is not None:
        if existing.check_status != "DRAFT":
            raise ConflictError(
                message="当天已存在相同金额的对账单",
                message_key="errors.autotask.statement.duplicate_key",
            )
        bill = existing
        instance = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.id == bill.process_instance_id,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one()
        bill.last_error = None
        instance.last_error_code = None
        instance.last_error_message = None
        instance.summary = dumps_json(summary)
        instance.status = ProcessInstanceStatus.ACTIVE.value
        instance.stage = ProcessStage.STMT_GENERATING.value
    else:
        instance = ProcessInstance(
            tenant_id=tenant_id,
            process_code=PROCESS_CODE,
            biz_key=f"DRAFT-{uuid.uuid4().hex[:12].upper()}",
            title=f"待生成对账单 {local_amount}",
            portal_account_id=portal_account_id,
            stage=ProcessStage.STMT_GENERATING.value,
            status=ProcessInstanceStatus.ACTIVE.value,
            line_total=len(lines),
            line_done=0,
            summary=dumps_json(summary),
            created_by=actor,
        )
        db.add(instance)
        await db.flush()
        bill = StatementBill(
            tenant_id=tenant_id,
            process_instance_id=instance.id,
            portal_account_id=portal_account_id,
            check_date=check_date,
            check_amount=local_amount,
            check_status="DRAFT",
            invoice_status="NOT_UPLOADED",
            sdms_check_head_id=check_head_id,
            last_error=None,
            created_by=actor,
        )
        db.add(bill)
        await db.flush()

    task = await _create_standalone_task(
        db,
        tenant_id=tenant_id,
        portal_account_id=portal_account_id,
        template_code=process_svc.STMT_GENERATE_TEMPLATE_CODE,
        title="对账单：生成对账单",
        task_input={
            "dateStart": date_start,
            "dateEnd": date_end,
            "lines": lines,
            "localAmount": str(local_amount),
            "sdmsCheckHeadId": check_head_id,
            "sdmsCheckNum": check_num,
            "billId": bill.id,
        },
        actor=actor,
        process_instance_id=instance.id,
    )
    await db.commit()
    await db.refresh(task)
    await db.refresh(instance)
    await db.refresh(bill)
    return {
        "ok": True,
        "instance_id": instance.id,
        "task_id": task.id,
        "bill_id": bill.id,
        "local_amount": str(local_amount),
        "sdms_amount": str(sdms_amount),
        "sdms_check_head_id": check_head_id,
        "sdms_check_num": check_num,
    }


async def retry_generate(
    db: AsyncSession,
    tenant_id: str,
    bill_id: str,
    *,
    actor: str,
) -> dict[str, Any]:
    """待生成草稿重新发起 SRM 生成。"""
    bill = await get_bill(db, tenant_id, bill_id)
    if bill.check_status != "DRAFT":
        raise BadRequestError(
            message="仅待生成草稿可重新生成",
            message_key="errors.autotask.statement.retry_draft_only",
        )
    instance = (
        await db.execute(
            select(ProcessInstance).where(
                ProcessInstance.id == bill.process_instance_id,
                not_deleted(ProcessInstance),
            )
        )
    ).scalar_one_or_none()
    if instance is None:
        raise NotFoundError(message="流程实例不存在", message_key="errors.autotask.process_instance_not_found")
    summary = loads_json(instance.summary, {})
    lines = summary.get("lines")
    if not isinstance(lines, list) or not lines:
        raise BadRequestError(
            message="草稿缺少勾选行，请回到生成页重新发起",
            message_key="errors.autotask.statement.retry_lines_missing",
        )
    bill.last_error = None
    instance.last_error_code = None
    instance.last_error_message = None
    instance.status = ProcessInstanceStatus.ACTIVE.value
    instance.stage = ProcessStage.STMT_GENERATING.value
    task = await _create_standalone_task(
        db,
        tenant_id=tenant_id,
        portal_account_id=bill.portal_account_id,
        template_code=process_svc.STMT_GENERATE_TEMPLATE_CODE,
        title="对账单：重新生成对账单",
        task_input={
            "dateStart": summary.get("date_start"),
            "dateEnd": summary.get("date_end"),
            "lines": lines,
            "localAmount": str(bill.check_amount),
            "sdmsCheckHeadId": bill.sdms_check_head_id,
            "sdmsCheckNum": summary.get("sdms_check_num"),
            "billId": bill.id,
        },
        actor=actor,
        process_instance_id=instance.id,
    )
    await db.commit()
    await db.refresh(task)
    return {
        "ok": True,
        "instance_id": instance.id,
        "task_id": task.id,
        "bill_id": bill.id,
        "local_amount": str(bill.check_amount),
    }


async def get_bill(db: AsyncSession, tenant_id: str, bill_id: str) -> StatementBill:
    bill = (
        await db.execute(
            select(StatementBill).where(
                StatementBill.id == bill_id,
                StatementBill.tenant_id == tenant_id,
                not_deleted(StatementBill),
            )
        )
    ).scalar_one_or_none()
    if bill is None:
        raise NotFoundError(message="对账单不存在", message_key="errors.autotask.statement.not_found")
    return bill


async def get_bill_instance(db: AsyncSession, process_instance_id: str) -> ProcessInstance | None:
    return (
        await db.execute(
            select(ProcessInstance).where(
                ProcessInstance.id == process_instance_id,
                not_deleted(ProcessInstance),
            )
        )
    ).scalar_one_or_none()


def receipt_lines_from_summary(summary: object) -> list[dict[str, Any]]:
    data = summary if isinstance(summary, dict) else loads_json(summary, {})
    if not isinstance(data, dict):
        return []
    lines = data.get("lines")
    if not isinstance(lines, list):
        return []
    return [item for item in lines if isinstance(item, dict)]


def sdms_check_num_from_summary(summary: object) -> str | None:
    data = summary if isinstance(summary, dict) else loads_json(summary, {})
    if not isinstance(data, dict):
        return None
    text = str(data.get("sdms_check_num") or "").strip()
    return text or None


def invoice_scan_from_summary(summary: object) -> dict[str, Any]:
    data = summary if isinstance(summary, dict) else loads_json(summary, {})
    if not isinstance(data, dict):
        return {}
    scan = data.get("invoice_scan")
    return scan if isinstance(scan, dict) else {}


def scanned_file_paths_from_summary(summary: object) -> list[str]:
    raw = invoice_scan_from_summary(summary).get("filePaths")
    if not isinstance(raw, list):
        return []
    return [str(path).strip() for path in raw if str(path).strip()]


def normalize_invoice_file_paths(paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in paths:
        text = str(item or "").strip()
        if not text:
            continue
        normalized.append(str(Path(text).expanduser()).casefold())
    return normalized


def to_list_item(
    bill: StatementBill,
    instance: ProcessInstance | None = None,
) -> StatementBillListItem:
    item = StatementBillListItem.model_validate(bill)
    if instance is None:
        return item
    return item.model_copy(
        update={
            "stage": instance.stage,
            "instance_status": instance.status,
            "last_error_code": instance.last_error_code,
            "last_error": bill.last_error or instance.last_error_message,
        }
    )


def to_detail(
    bill: StatementBill,
    instance: ProcessInstance | None,
    *,
    sub_tasks: list,
    stage_history: list,
) -> StatementBillDetail:
    item = to_list_item(bill, instance)
    history_items = [
        entry
        if isinstance(entry, ProcessStageHistoryResponse)
        else ProcessStageHistoryResponse.model_validate(entry)
        for entry in stage_history
    ]
    task_items = [
        task if isinstance(task, ProcessSubTaskResponse) else ProcessSubTaskResponse.model_validate(task)
        for task in sub_tasks
    ]
    return StatementBillDetail.model_validate(
        {
            **item.model_dump(),
            "sdms_check_head_id": bill.sdms_check_head_id,
            "sdms_check_num": sdms_check_num_from_summary(
                instance.summary if instance else None
            ),
            "scanned_file_paths": scanned_file_paths_from_summary(
                instance.summary if instance else None
            ),
            "lines": receipt_lines_from_summary(instance.summary if instance else None),
            "sub_tasks": task_items,
            "stage_history": history_items,
        }
    )


async def list_bills(
    db: AsyncSession,
    tenant_id: str,
    *,
    check_status: str | None = None,
    stage: str | None = None,
    accessible_portal_ids: list[str] | None = None,
) -> list[tuple[StatementBill, ProcessInstance | None]]:
    query = (
        select(StatementBill, ProcessInstance)
        .outerjoin(
            ProcessInstance,
            ProcessInstance.id == StatementBill.process_instance_id,
        )
        .where(
            StatementBill.tenant_id == tenant_id,
            not_deleted(StatementBill),
        )
    )
    if check_status:
        query = query.where(StatementBill.check_status == check_status)
    if stage:
        query = query.where(
            ProcessInstance.stage == stage,
            not_deleted(ProcessInstance),
        )
    from app.services.permission_service import apply_accessible_portal_filter

    query = apply_accessible_portal_filter(
        query, StatementBill.portal_account_id, accessible_portal_ids
    )
    result = await db.execute(query.order_by(StatementBill.created_at.desc()))
    return [(bill, instance) for bill, instance in result.all()]


def require_invoice_file_paths(file_paths: list[str]) -> list[str]:
    if not file_paths:
        raise BadRequestError(
            message="请选择发票文件",
            message_key="errors.autotask.statement.invoice_files_required",
        )
    if len(file_paths) > 10:
        raise BadRequestError(
            message="最多上传 10 个发票文件",
            message_key="errors.autotask.statement.invoice_files_limit",
        )
    return file_paths


async def upload_invoice(
    db: AsyncSession,
    tenant_id: str,
    bill_id: str,
    *,
    file_paths: list[str],
    actor: str,
) -> AutomationTask:
    bill = await get_bill(db, tenant_id, bill_id)
    if bill.check_status == "VOID":
        raise BadRequestError(
            message="已作废对账单不可上传发票",
            message_key="errors.autotask.statement.void_readonly",
        )
    if bill.check_status == "DRAFT":
        raise BadRequestError(
            message="待生成草稿尚未在 SRM 生成成功，不能上传发票",
            message_key="errors.autotask.statement.draft_no_invoice",
        )
    paths = require_invoice_file_paths(file_paths)
    task = await _create_standalone_task(
        db,
        tenant_id=tenant_id,
        portal_account_id=bill.portal_account_id,
        template_code=process_svc.STMT_UPLOAD_INVOICE_TEMPLATE_CODE,
        title="对账单：扫描发票",
        task_input={
            "checkDate": bill.check_date.isoformat(),
            "checkAmount": str(bill.check_amount),
            "filePaths": paths,
            "billId": bill.id,
        },
        actor=actor,
        process_instance_id=bill.process_instance_id,
    )
    await db.commit()
    await db.refresh(task)
    return task


async def submit_review(
    db: AsyncSession,
    tenant_id: str,
    bill_id: str,
    *,
    file_paths: list[str],
    actor: str,
    sdms_username: str = "",
) -> AutomationTask:
    bill = await get_bill(db, tenant_id, bill_id)
    if bill.check_status == "VOID":
        raise BadRequestError(
            message="已作废对账单不可提交审核",
            message_key="errors.autotask.statement.void_readonly",
        )
    if bill.check_status == "DRAFT":
        raise BadRequestError(
            message="待生成草稿尚未在 SRM 生成成功，不能提交审核",
            message_key="errors.autotask.statement.draft_no_submit",
        )
    expected_no = str(bill.invoice_no or "").strip()
    expected_amount = bill.invoice_amount
    if not expected_no or expected_amount is None:
        raise BadRequestError(
            message="请先扫描发票，并核对页面上的发票号和发票总额后再提交",
            message_key="errors.autotask.statement.scan_before_submit",
        )
    paths = require_invoice_file_paths(file_paths)
    instance = await get_bill_instance(db, bill.process_instance_id)
    scanned_paths = scanned_file_paths_from_summary(
        instance.summary if instance else None
    )
    if scanned_paths and normalize_invoice_file_paths(paths) != normalize_invoice_file_paths(
        scanned_paths
    ):
        raise BadRequestError(
            message="发票文件已更换，请重新扫描后再提交审核",
            message_key="errors.autotask.statement.invoice_files_changed",
        )
    task = await _create_standalone_task(
        db,
        tenant_id=tenant_id,
        portal_account_id=bill.portal_account_id,
        template_code=process_svc.STMT_SUBMIT_REVIEW_TEMPLATE_CODE,
        title="对账单：提交审核",
        task_input={
            "checkDate": bill.check_date.isoformat(),
            "checkAmount": str(bill.check_amount),
            "filePaths": paths,
            "billId": bill.id,
            "expectedInvoiceNo": expected_no,
            "expectedInvoiceAmount": str(expected_amount),
            "sdmsCheckNum": sdms_check_num_from_summary(
                instance.summary if instance else None
            ),
            "sdmsUsername": str(sdms_username or "").strip(),
        },
        actor=actor,
        process_instance_id=bill.process_instance_id,
    )
    await db.commit()
    await db.refresh(task)
    return task


async def cancel_statement(
    db: AsyncSession,
    tenant_id: str,
    bill_id: str,
    *,
    actor: str,
) -> StatementBill:
    """仅本地作废，不触发 SRM。"""
    bill = await get_bill(db, tenant_id, bill_id)
    if bill.check_status == "VOID":
        return bill
    if bill.check_status == "CHECKED":
        raise BadRequestError(
            message="已对账单据不可取消",
            message_key="errors.autotask.statement.checked_cannot_cancel",
        )
    bill.check_status = "VOID"
    bill.last_error = None
    instance = (
        await db.execute(
            select(ProcessInstance).where(
                ProcessInstance.id == bill.process_instance_id,
                not_deleted(ProcessInstance),
            )
        )
    ).scalar_one_or_none()
    if instance is not None:
        process_svc._change_stage(
            db,
            instance,
            ProcessStage.STMT_CANCELLED,
            actor=actor,
            note="取消对账（仅本地）",
        )
        instance.status = ProcessInstanceStatus.CANCELLED.value
    await db.commit()
    await db.refresh(bill)
    return bill


_MONEY_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_optional_money(raw: object) -> Decimal | None:
    """Parse OCR/RPA money text. Empty or non-numeric values return None instead of raising."""
    if raw is None:
        return None
    text = (
        str(raw)
        .strip()
        .replace(",", "")
        .replace("，", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("元", "")
    )
    if not text:
        return None
    match = _MONEY_RE.search(text)
    if match is None:
        return None
    try:
        return Decimal(match.group(0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _parse_check_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return date.today()
    return date.fromisoformat(text[:10])


def is_uncommitted_output(output: Any) -> bool:
    """演练 dryRun 找到写按钮但不 click 时，output.committed 为 False。"""
    return isinstance(output, dict) and output.get("committed") is False


def is_uncommitted_generate_output(output: Any) -> bool:
    return is_uncommitted_output(output)


async def on_generate_finished(db: AsyncSession, task: AutomationTask, run: RpaRun) -> None:
    if not task.process_instance_id:
        return
    instance = (
        await db.execute(
            select(ProcessInstance)
            .where(ProcessInstance.id == task.process_instance_id, not_deleted(ProcessInstance))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if instance is None:
        return
    bill = (
        await db.execute(
            select(StatementBill)
            .where(
                StatementBill.process_instance_id == instance.id,
                not_deleted(StatementBill),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    fail_message = run.error_message or "生成对账单失败"
    if run.status != RunStatus.SUCCESS.value:
        instance.last_error_code = run.error_code
        instance.last_error_message = fail_message
        instance.status = ProcessInstanceStatus.ACTIVE.value
        if bill is not None:
            bill.last_error = fail_message
        return

    output = run.output if isinstance(run.output, dict) else {}
    if is_uncommitted_generate_output(output):
        summary = loads_json(instance.summary, {})
        if not isinstance(summary, dict):
            summary = {}
        summary["drill"] = {
            "uncommitted": True,
            "blockedAction": output.get("blockedAction") or "generate_statement",
            "generateButtonFound": bool(output.get("generateButtonFound")),
        }
        instance.summary = dumps_json(summary)
        instance.last_error_code = None
        instance.last_error_message = None
        instance.status = ProcessInstanceStatus.ACTIVE.value
        if bill is not None:
            bill.check_status = "DRAFT"
            bill.last_error = None
        return

    check_date = _parse_check_date(output.get("checkDate") or output.get("check_date"))
    raw_amount = output.get("checkAmount") or output.get("check_amount")
    if raw_amount is None:
        instance.last_error_code = "STMT_OUTPUT_AMOUNT_MISSING"
        instance.last_error_message = "生成对账单成功输出缺少对账金额"
        if bill is not None:
            bill.last_error = instance.last_error_message
        return
    check_amount = Decimal(str(raw_amount)).quantize(Decimal("0.01"))
    summary = loads_json(instance.summary, {})
    if bill is None:
        bill = StatementBill(
            tenant_id=instance.tenant_id,
            process_instance_id=instance.id,
            portal_account_id=instance.portal_account_id,
            check_date=check_date,
            check_amount=check_amount,
            check_status="UNCHECKED",
            invoice_status="NOT_UPLOADED",
            sdms_check_head_id=summary.get("sdms_check_head_id"),
            created_by=task.created_by,
        )
        db.add(bill)
    else:
        bill.check_date = check_date
        bill.check_amount = check_amount
        bill.check_status = "UNCHECKED"
        bill.last_error = None
        if summary.get("sdms_check_head_id"):
            bill.sdms_check_head_id = summary.get("sdms_check_head_id")
    instance.biz_key = f"{check_date.isoformat()}|{check_amount}"
    instance.title = f"对账单 {check_date.isoformat()} / {check_amount}"
    instance.last_error_code = None
    instance.last_error_message = None
    instance.status = ProcessInstanceStatus.ACTIVE.value
    process_svc._change_stage(
        db,
        instance,
        ProcessStage.STMT_PENDING_INVOICE,
        actor="system",
        note="生成对账单成功",
    )


async def on_upload_finished(db: AsyncSession, task: AutomationTask, run: RpaRun) -> None:
    task_input = loads_json(task.input, {})
    bill_id = str(task_input.get("billId") or "").strip()
    if not bill_id:
        return
    bill = (
        await db.execute(
            select(StatementBill)
            .where(StatementBill.id == bill_id, not_deleted(StatementBill))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if bill is None:
        return

    if run.status != RunStatus.SUCCESS.value:
        bill.last_error = run.error_message or "扫描发票失败"
        return

    output = run.output if isinstance(run.output, dict) else {}
    invoice_no = str(output.get("invoiceNo") or output.get("invoice_no") or "").strip() or None
    raw_amount = output.get("invoiceAmount")
    if raw_amount is None:
        raw_amount = output.get("invoice_amount")
    invoice_amount = parse_optional_money(raw_amount)
    if not invoice_no or invoice_amount is None:
        bill.last_error = "扫描成功但未回写发票号或发票总额"
        return
    bill.invoice_no = invoice_no
    bill.invoice_amount = invoice_amount
    bill.invoice_status = "UPLOADED"
    bill.check_status = "UNCHECKED"
    bill.last_error = None
    if task.process_instance_id:
        instance = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.id == task.process_instance_id,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one_or_none()
        if instance is not None:
            summary = loads_json(instance.summary, {})
            if not isinstance(summary, dict):
                summary = {}
            summary["invoice_scan"] = {
                "filePaths": [
                    str(path).strip()
                    for path in (task_input.get("filePaths") or [])
                    if str(path).strip()
                ],
                "invoiceNo": invoice_no,
                "invoiceAmount": str(invoice_amount),
            }
            instance.summary = dumps_json(summary)
            instance.last_error_code = None
            instance.last_error_message = None
            instance.status = ProcessInstanceStatus.ACTIVE.value


async def on_submit_finished(db: AsyncSession, task: AutomationTask, run: RpaRun) -> None:
    task_input = loads_json(task.input, {})
    bill_id = str(task_input.get("billId") or "").strip()
    if not bill_id:
        return
    bill = (
        await db.execute(
            select(StatementBill)
            .where(StatementBill.id == bill_id, not_deleted(StatementBill))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if bill is None:
        return

    if run.status != RunStatus.SUCCESS.value:
        bill.last_error = run.error_message or "提交审核失败"
        return

    output = run.output if isinstance(run.output, dict) else {}
    if is_uncommitted_output(output):
        instance = None
        if task.process_instance_id:
            instance = (
                await db.execute(
                    select(ProcessInstance).where(
                        ProcessInstance.id == task.process_instance_id,
                        not_deleted(ProcessInstance),
                    )
                )
            ).scalar_one_or_none()
        if instance is not None:
            summary = loads_json(instance.summary, {})
            if not isinstance(summary, dict):
                summary = {}
            existing_drill = summary.get("drill") if isinstance(summary.get("drill"), dict) else {}
            summary["drill"] = {
                "uncommitted": True,
                "shadow": bool(existing_drill.get("shadow")),
                "step": "srm.stmt.submit_review",
                "blockedAction": output.get("blockedAction") or "submit_review",
                "submitButtonFound": bool(output.get("submitButtonFound")),
            }
            instance.summary = dumps_json(summary)
            instance.last_error_code = None
            instance.last_error_message = None
            instance.status = ProcessInstanceStatus.ACTIVE.value
        bill.check_status = "UNCHECKED"
        bill.invoice_status = "NOT_UPLOADED"
        bill.last_error = None
        return

    invoice_no = str(output.get("invoiceNo") or output.get("invoice_no") or "").strip() or None
    raw_amount = output.get("invoiceAmount")
    if raw_amount is None:
        raw_amount = output.get("invoice_amount")
    bill.invoice_no = invoice_no
    bill.invoice_amount = parse_optional_money(raw_amount)
    bill.check_status = "CHECKED"
    bill.invoice_status = "REVIEWING"
    bill.last_error = None

    instance = None
    if task.process_instance_id:
        instance = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.id == task.process_instance_id,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one_or_none()
        if instance is not None:
            process_svc._change_stage(
                db,
                instance,
                ProcessStage.STMT_SUBMITTED,
                actor="system",
                note="提交审核成功",
            )
            instance.status = ProcessInstanceStatus.COMPLETED.value

    check_num = str(task_input.get("sdmsCheckNum") or "").strip()
    if not check_num:
        check_num = sdms_check_num_from_summary(instance.summary if instance else None) or ""
    raw_paths = task_input.get("filePaths")
    paths = (
        [str(path).strip() for path in raw_paths if str(path).strip()]
        if isinstance(raw_paths, list)
        else []
    )
    attach_error = await upload_statement_invoices_to_sdms(
        check_num=check_num,
        username=str(task_input.get("sdmsUsername") or "").strip(),
        file_paths=paths,
    )
    if attach_error:
        bill.last_error = attach_error


async def dispatch_statement_finished(db: AsyncSession, task: AutomationTask, run: RpaRun) -> bool:
    """若为对账单子任务则处理并返回 True。"""
    if task.task_type == process_svc.STMT_GENERATE_TEMPLATE_CODE:
        await on_generate_finished(db, task, run)
        return True
    if task.task_type == process_svc.STMT_UPLOAD_INVOICE_TEMPLATE_CODE:
        await on_upload_finished(db, task, run)
        return True
    if task.task_type == process_svc.STMT_SUBMIT_REVIEW_TEMPLATE_CODE:
        await on_submit_finished(db, task, run)
        return True
    if task.task_type == process_svc.STMT_QUERY_RECEIPTS_TEMPLATE_CODE:
        return True
    return False
