"""京东方发票箱单：匹配交货计划、读 WMS、推进 RPA 节点。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.boe_packing import (
    EDITABLE_STAGES,
    ENRICH_TEMPLATE_CODE,
    EXPECTED_ORG_CODE,
    IN_FLIGHT_TASK_STATUSES,
    PROCESS_CODE,
    RPA_TEMPLATE_CODES,
    RETRYABLE_STAGES,
    SAVE_DRAFT_TEMPLATE_CODE,
    SUBMIT_TEMPLATE_CODE,
    VOL_UNIT,
)
from sqlalchemy.exc import ProgrammingError

from app.domain.portal_category import PortalCategory
from app.services import region_code_map_service
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import (
    PortalAccountStatus,
    ProcessInstanceStatus,
    ProcessStage,
    RunStatus,
    TaskStatus,
)
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.models.rpa_run import RpaRun
from app.models.user_cache import UserCache
from app.services import boe_smc_client
from app.services import integration_call_log_service
from app.services.json_utils import dumps_json, loads_json
from app.services.process_instance_service import (
    _change_stage,
    _clear_instance_error,
    _create_sub_task,
    _set_instance_error,
    get_instance,
    list_stage_history,
    list_sub_tasks,
    to_sub_task_response,
)

# @lat: [[domain#BoeInvoicePacking]]


def _now() -> datetime:
    return datetime.now(UTC)


def _summary(instance: ProcessInstance) -> dict[str, Any]:
    data = loads_json(instance.summary, {})
    return data if isinstance(data, dict) else {}


def _save_summary(instance: ProcessInstance, summary: dict[str, Any]) -> None:
    instance.summary = dumps_json(summary)


def _qty(value: Any) -> Decimal | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _date_part(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return text[:10]


def _pick_field(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key not in item or item[key] is None:
            continue
        text = str(item[key]).strip()
        if text:
            return text
    return ""


def _format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _wms_line_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        nested = payload.get("list")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        return [payload]
    return []


def _qty_mismatch(deliver_qty: Any, lines: list[dict[str, Any]]) -> tuple[bool, str, str]:
    planned = _qty(deliver_qty)
    total = Decimal("0")
    for line in lines:
        part = _qty(line.get("deliveryQty"))
        if part is not None:
            total += part
    planned_text = str(planned) if planned is not None else str(deliver_qty or "")
    total_text = format(total, "f")
    if planned is None:
        return False, planned_text, total_text
    return planned != total, planned_text, total_text


def _header_from_plan(row: dict[str, Any], *, matched_at: datetime) -> dict[str, Any]:
    invoice_date = _date_part(str(row.get("deliver_date") or ""))
    clock = matched_at.astimezone().strftime("%H:%M:%S")
    etd = f"{invoice_date} {clock}" if invoice_date else ""
    consign = ""
    if invoice_date:
        try:
            day = datetime.fromisoformat(invoice_date).date() + timedelta(days=5)
            consign = day.isoformat()
        except ValueError:
            consign = ""
    return {
        "aiRecognize": False,
        "invoiceNo": str(row.get("doc_no") or "").strip(),
        "factory": str(row.get("boe_factory") or "").strip(),
        "invoiceDate": invoice_date,
        "etd": etd,
        "consignArrivalDate": consign,
        "totalVol": "",
        "volUnit": VOL_UNIT,
    }


def _lines_from_wms(payload: Any) -> tuple[str, list[dict[str, Any]]]:
    rows = _wms_line_rows(payload)
    lines: list[dict[str, Any]] = []
    cubic_sum = Decimal("0")
    has_cubic = False
    for index, item in enumerate(rows, start=1):
        cubic = _qty(item.get("cubic"))
        if cubic is not None:
            cubic_sum += cubic
            has_cubic = True
        lines.append(
            {
                "lineNo": str(index),
                "poNum": _pick_field(item, "cuspo", "po_num", "poNum"),
                "itemNum": _pick_field(item, "cusitem", "item_num", "itemNum"),
                "deliveryQty": _pick_field(item, "qty", "delivery_qty", "deliveryQty"),
                "netWeight": _pick_field(
                    item, "netweight", "net_weight", "net_Weight", "netWeight"
                ),
                "regionCode": _pick_field(item, "coo", "region", "regionCode"),
                "regionSrmName": "",
                "lineItem": "",
                "remainingQty": "",
                "itemName": "",
            }
        )
    if has_cubic:
        total_vol = _format_decimal(cubic_sum)
    elif isinstance(payload, dict):
        total_vol = _pick_field(payload, "total_vol", "totalVol")
    else:
        total_vol = ""
    return total_vol, lines


async def _portal_by_subcode(
    db: AsyncSession, tenant_id: str, subcode: str
) -> PortalAccount | None:
    return (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.tenant_id == tenant_id,
                PortalAccount.category == PortalCategory.BOE.value,
                PortalAccount.erp_entity_code == subcode,
                PortalAccount.status == PortalAccountStatus.ENABLED.value,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()


async def _existing_instance(
    db: AsyncSession, portal_id: str, doc_no: str
) -> ProcessInstance | None:
    return (
        await db.execute(
            select(ProcessInstance).where(
                ProcessInstance.portal_account_id == portal_id,
                ProcessInstance.process_code == PROCESS_CODE,
                ProcessInstance.biz_key == doc_no,
                ProcessInstance.status != ProcessInstanceStatus.CANCELLED.value,
                not_deleted(ProcessInstance),
            )
        )
    ).scalar_one_or_none()


def _portal_fields(portal: PortalAccount) -> dict[str, str]:
    return {
        "customerName": portal.erp_entity_name,
        "customerSubcode": portal.erp_entity_code,
        "businessEntity": portal.business_entity,
        "ou": portal.ou,
        "loginAccount": portal.login_account,
    }


def _apply_qty_warning(summary: dict[str, Any], deliver_qty: Any, lines: list[dict[str, Any]]) -> None:
    mismatch, planned, actual = _qty_mismatch(deliver_qty, lines)
    summary["deliverQty"] = planned
    summary["wmsQtySum"] = actual
    summary["qtyMismatch"] = mismatch
    if mismatch:
        summary["qtyWarning"] = f"WMS 行数量之和 {actual} 与交货计划合计 {planned} 不一致"
    else:
        summary.pop("qtyWarning", None)


def qty_is_aligned(summary: dict[str, Any]) -> bool:
    return not bool(summary.get("qtyMismatch"))


async def list_instances(
    db: AsyncSession,
    tenant_id: str,
    *,
    stage: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    accessible_portal_ids: list[str] | None = None,
) -> list[ProcessInstance]:
    query = (
        select(ProcessInstance)
        .join(PortalAccount, PortalAccount.id == ProcessInstance.portal_account_id)
        .where(
            ProcessInstance.tenant_id == tenant_id,
            ProcessInstance.process_code == PROCESS_CODE,
            PortalAccount.category == PortalCategory.BOE.value,
            not_deleted(ProcessInstance),
            not_deleted(PortalAccount),
        )
    )
    if stage:
        query = query.where(ProcessInstance.stage == stage)
    if status:
        query = query.where(ProcessInstance.status == status)
    if keyword:
        query = query.where(ProcessInstance.biz_key.contains(keyword.strip()))
    from app.services.permission_service import apply_accessible_portal_filter

    query = apply_accessible_portal_filter(
        query, ProcessInstance.portal_account_id, accessible_portal_ids
    )
    result = await db.execute(query.order_by(ProcessInstance.created_at.desc()))
    return list(result.scalars().all())


async def get_packing_instance(
    db: AsyncSession, tenant_id: str, instance_id: str
) -> ProcessInstance:
    instance = await get_instance(db, tenant_id, instance_id)
    if instance.process_code != PROCESS_CODE:
        raise NotFoundError(message="流程实例不存在", message_key="errors.autotask.process_instance_not_found")
    return instance


def to_list_item(instance: ProcessInstance, portal: PortalAccount | None = None) -> dict[str, Any]:
    summary = _summary(instance)
    header = summary.get("header") if isinstance(summary.get("header"), dict) else {}
    return {
        "id": instance.id,
        "process_code": instance.process_code,
        "biz_key": instance.biz_key,
        "title": instance.title,
        "portal_account_id": instance.portal_account_id,
        "stage": instance.stage,
        "status": instance.status,
        "line_total": instance.line_total,
        "line_done": instance.line_done,
        "last_error_code": instance.last_error_code,
        "last_error_message": instance.last_error_message,
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
        "qty_mismatch": bool(summary.get("qtyMismatch")),
        "invoice_no": header.get("invoiceNo") or instance.biz_key,
        "factory": header.get("factory") or "",
        "customer_name": (portal.erp_entity_name if portal else ""),
    }


async def to_detail(
    db: AsyncSession, instance: ProcessInstance, portal: PortalAccount
) -> dict[str, Any]:
    summary = _summary(instance)
    header = dict(summary.get("header") or {})
    header.update(_portal_fields(portal))
    if not header.get("volUnit"):
        header["volUnit"] = VOL_UNIT
    header["aiRecognize"] = False
    history = await list_stage_history(db, instance.id)
    sub_tasks = await list_sub_tasks(db, instance.id)
    return {
        "id": instance.id,
        "processCode": instance.process_code,
        "bizKey": instance.biz_key,
        "title": instance.title,
        "portalAccountId": instance.portal_account_id,
        "stage": instance.stage,
        "status": instance.status,
        "lineTotal": instance.line_total,
        "lineDone": instance.line_done,
        "lastErrorCode": instance.last_error_code,
        "lastErrorMessage": instance.last_error_message,
        "createdAt": instance.created_at,
        "updatedAt": instance.updated_at,
        "header": header,
        "lines": summary.get("lines") or [],
        "qtyMismatch": bool(summary.get("qtyMismatch")),
        "qtyWarning": summary.get("qtyWarning"),
        "orgCodeWarning": summary.get("orgCodeWarning"),
        "srmDraftNo": summary.get("srmDraftNo") or "",
        "reviewBaseline": summary.get("reviewBaseline"),
        "stageHistory": [
            {
                "id": item.id,
                "fromStage": item.from_stage,
                "toStage": item.to_stage,
                "actor": item.actor,
                "note": item.note,
                "createdAt": item.created_at,
            }
            for item in history
        ],
        "subTasks": [to_sub_task_response(task) for task in sub_tasks],
    }


async def _log_smc(
    db: AsyncSession,
    *,
    tenant_id: str,
    task_id: str | None,
    method: str,
    result: boe_smc_client.SmcHttpResult,
    request_body: str | None = None,
) -> None:
    await integration_call_log_service.record_httpx_exchange(
        db,
        task_id=task_id,
        tenant_id=tenant_id,
        run_id=None,
        system="SMC",
        method=method,
        url=result.url,
        request_body=request_body,
        response_or_exc=None,
        status_code=result.status_code,
        error_code="SMC_ERROR" if result.error else None,
        duration_ms=None,
        commit=False,
    )


async def fetch_wms_for_instance(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    actor: str,
) -> ProcessInstance:
    if instance.stage != ProcessStage.BOE_PACK_FETCH_WMS.value:
        raise BadRequestError(
            message="当前阶段不能读 WMS",
            message_key="errors.autotask.boe_pack.stage_invalid",
        )
    result = await boe_smc_client.fetch_wms_packing(instance.biz_key)
    await _log_smc(
        db,
        tenant_id=instance.tenant_id,
        task_id=None,
        method="GET",
        result=result,
        request_body=dumps_json({"doc_no": instance.biz_key}),
    )
    summary = _summary(instance)
    summary["wmsCall"] = {
        "url": result.url,
        "statusCode": result.status_code,
        "error": result.error,
    }
    if result.error or not result.data:
        _save_summary(instance, summary)
        _set_instance_error(
            instance,
            error_code="BOE_WMS_FETCH_FAILED",
            error_message=result.error or "WMS 无数据",
        )
        await db.commit()
        await db.refresh(instance)
        return instance

    total_vol, lines = _lines_from_wms(result.data)
    maps: dict[str, str] = {}
    try:
        maps = await region_code_map_service.mapping_dict(
            db, instance.tenant_id, PortalCategory.BOE.value
        )
    except ProgrammingError:
        maps = {}
    for line in lines:
        code = str(line.get("regionCode") or "")
        line["regionSrmName"] = maps.get(code, "")
    header = dict(summary.get("header") or {})
    header["totalVol"] = total_vol
    header["volUnit"] = VOL_UNIT
    summary["header"] = header
    summary["lines"] = lines
    _apply_qty_warning(summary, summary.get("deliverQty"), lines)
    instance.line_total = len(lines)
    instance.line_done = 0
    _save_summary(instance, summary)
    _clear_instance_error(instance)
    _change_stage(
        db,
        instance,
        ProcessStage.BOE_PACK_ENRICH,
        actor=actor,
        note="WMS 行/体积已落",
    )
    await _maybe_enqueue_rpa(
        db,
        instance,
        template_code=ENRICH_TEMPLATE_CODE,
        title=f"RPA 补全项目信息行 - {instance.biz_key}",
        actor=actor,
        required=False,
    )
    await db.commit()
    await db.refresh(instance)
    return instance


async def _maybe_enqueue_rpa(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    template_code: str,
    title: str,
    actor: str,
    required: bool,
) -> AutomationTask | None:
    inflight = (
        await db.execute(
            select(AutomationTask.id).where(
                AutomationTask.process_instance_id == instance.id,
                AutomationTask.task_type == template_code,
                AutomationTask.status.in_(tuple(IN_FLIGHT_TASK_STATUSES)),
                not_deleted(AutomationTask),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if inflight is not None:
        return None
    try:
        task_input = {
            "instanceId": instance.id,
            "docNo": instance.biz_key,
            "summary": _summary(instance),
        }
        return await _create_sub_task(
            db,
            instance,
            template_code=template_code,
            title=title,
            task_input=task_input,
            actor=actor,
        )
    except BadRequestError:
        if required:
            raise
        return None


async def match_delivery_plans(
    db: AsyncSession,
    tenant_id: str,
    *,
    actor: str,
) -> dict[str, Any]:
    result = await boe_smc_client.fetch_delivery_plans()
    await _log_smc(
        db,
        tenant_id=tenant_id,
        task_id=None,
        method="POST",
        result=result,
        request_body="{}",
    )
    created: list[str] = []
    skipped: list[dict[str, str]] = []
    missing_portal: list[str] = []
    if result.error:
        await db.commit()
        return {
            "created_count": 0,
            "skipped_count": 0,
            "missing_portal": [],
            "error": result.error,
            "created_ids": [],
        }

    matched_at = _now()
    for row in result.data:
        doc_no = str(row.get("doc_no") or "").strip()
        subcode = str(row.get("party_site_number") or "").strip()
        if not doc_no or not subcode:
            skipped.append({"docNo": doc_no, "reason": "missing_doc_or_subcode"})
            continue
        portal = await _portal_by_subcode(db, tenant_id, subcode)
        if portal is None:
            missing_portal.append(subcode)
            skipped.append({"docNo": doc_no, "reason": f"no_portal:{subcode}"})
            continue
        existing = await _existing_instance(db, portal.id, doc_no)
        if existing is not None:
            skipped.append({"docNo": doc_no, "reason": "exists"})
            continue
        org_code = str(row.get("org_code") or "").strip()
        header = _header_from_plan(row, matched_at=matched_at)
        summary: dict[str, Any] = {
            "header": header,
            "lines": [],
            "deliverQty": str(row.get("deliver_qty") or "").strip(),
            "orgCode": org_code,
        }
        if org_code and org_code != EXPECTED_ORG_CODE:
            summary["orgCodeWarning"] = f"交易主体编号 {org_code} 不是 {EXPECTED_ORG_CODE}"
        instance = ProcessInstance(
            tenant_id=tenant_id,
            process_code=PROCESS_CODE,
            biz_key=doc_no,
            title=f"发票箱单 - {doc_no}",
            portal_account_id=portal.id,
            stage=ProcessStage.BOE_PACK_SCAN_PLAN.value,
            status=ProcessInstanceStatus.ACTIVE.value,
            line_total=0,
            line_done=0,
            summary=dumps_json(summary),
            created_by=actor,
        )
        db.add(instance)
        await db.flush()
        _change_stage(
            db,
            instance,
            ProcessStage.BOE_PACK_FETCH_WMS,
            actor=actor,
            note="匹配交货计划成功（仅头）",
        )
        await fetch_wms_for_instance(db, instance, actor=actor)
        created.append(instance.id)

    if not created:
        await db.commit()
    return {
        "created_count": len(created),
        "skipped_count": len(skipped),
        "missing_portal": sorted(set(missing_portal)),
        "error": None,
        "created_ids": created,
        "skipped": skipped,
    }


async def retry_instance(
    db: AsyncSession,
    tenant_id: str,
    instance_id: str,
    user: UserCache,
) -> ProcessInstance:
    instance = await get_packing_instance(db, tenant_id, instance_id)
    actor = user.user_id
    if instance.stage not in RETRYABLE_STAGES:
        raise BadRequestError(
            message="当前阶段不能重试",
            message_key="errors.autotask.boe_pack.retry_invalid",
        )
    if instance.stage == ProcessStage.BOE_PACK_FETCH_WMS.value:
        return await fetch_wms_for_instance(db, instance, actor=actor)
    template = {
        ProcessStage.BOE_PACK_ENRICH.value: (ENRICH_TEMPLATE_CODE, f"RPA 补全项目信息行 - {instance.biz_key}"),
        ProcessStage.BOE_PACK_SAVE_DRAFT.value: (SAVE_DRAFT_TEMPLATE_CODE, f"保存 SRM 草稿单 - {instance.biz_key}"),
        ProcessStage.BOE_PACK_SUBMITTING.value: (SUBMIT_TEMPLATE_CODE, f"提交 SRM 单据 - {instance.biz_key}"),
    }[instance.stage]
    await _maybe_enqueue_rpa(
        db,
        instance,
        template_code=template[0],
        title=template[1],
        actor=actor,
        required=True,
    )
    await db.commit()
    await db.refresh(instance)
    return instance


async def cancel_instance(
    db: AsyncSession,
    tenant_id: str,
    instance_id: str,
    user: UserCache,
) -> ProcessInstance:
    instance = await get_packing_instance(db, tenant_id, instance_id)
    if instance.status != ProcessInstanceStatus.ACTIVE.value:
        raise BadRequestError(
            message="仅进行中的单据可作废",
            message_key="errors.autotask.boe_pack.cancel_invalid",
        )
    actor = user.user_id
    instance.status = ProcessInstanceStatus.CANCELLED.value
    _change_stage(
        db,
        instance,
        ProcessStage.BOE_PACK_CANCELLED,
        actor=actor,
        note="客服作废",
    )
    await db.commit()
    await db.refresh(instance)
    return instance


def _editable_header(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"invoiceNo", "factory", "invoiceDate", "etd", "consignArrivalDate", "totalVol"}
    return {key: str(payload[key]).strip() for key in allowed if key in payload}


def _editable_line(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "lineNo",
        "poNum",
        "itemNum",
        "deliveryQty",
        "netWeight",
        "regionCode",
        "regionSrmName",
        "lineItem",
        "remainingQty",
        "itemName",
    }
    return {key: str(payload.get(key) or "").strip() for key in allowed}


async def patch_instance(
    db: AsyncSession,
    tenant_id: str,
    instance_id: str,
    body: dict[str, Any],
    user: UserCache,
) -> ProcessInstance:
    instance = await get_packing_instance(db, tenant_id, instance_id)
    if instance.stage not in EDITABLE_STAGES:
        raise BadRequestError(
            message="当前阶段不能改单",
            message_key="errors.autotask.boe_pack.patch_invalid",
        )
    summary = _summary(instance)
    header = dict(summary.get("header") or {})
    if isinstance(body.get("header"), dict):
        header.update(_editable_header(body["header"]))
        header["aiRecognize"] = False
        header["volUnit"] = VOL_UNIT
        summary["header"] = header
    if isinstance(body.get("lines"), list):
        summary["lines"] = [
            _editable_line(item) for item in body["lines"] if isinstance(item, dict)
        ]
        instance.line_total = len(summary["lines"])
    _apply_qty_warning(summary, summary.get("deliverQty"), summary.get("lines") or [])
    _save_summary(instance, summary)
    await db.commit()
    await db.refresh(instance)
    return instance


async def submit_instance(
    db: AsyncSession,
    tenant_id: str,
    instance_id: str,
    user: UserCache,
) -> ProcessInstance:
    instance = await get_packing_instance(db, tenant_id, instance_id)
    if instance.stage != ProcessStage.BOE_PACK_REVIEW.value:
        raise BadRequestError(
            message="仅客服核验阶段可提交",
            message_key="errors.autotask.boe_pack.submit_invalid",
        )
    summary = _summary(instance)
    if not qty_is_aligned(summary):
        raise BadRequestError(
            message=summary.get("qtyWarning") or "数量不一致，不能提交",
            message_key="errors.autotask.boe_pack.qty_mismatch",
        )
    actor = user.user_id
    _change_stage(
        db,
        instance,
        ProcessStage.BOE_PACK_SUBMITTING,
        actor=actor,
        note="客服提交",
    )
    await _maybe_enqueue_rpa(
        db,
        instance,
        template_code=SUBMIT_TEMPLATE_CODE,
        title=f"提交 SRM 单据 - {instance.biz_key}",
        actor=actor,
        required=True,
    )
    await db.commit()
    await db.refresh(instance)
    return instance


def _merge_enrich_output(summary: dict[str, Any], output: dict[str, Any]) -> None:
    lines_out = output.get("lines")
    if not isinstance(lines_out, list):
        return
    current = summary.get("lines") if isinstance(summary.get("lines"), list) else []
    by_key = {
        (str(line.get("poNum") or ""), str(line.get("itemNum") or "")): line
        for line in current
        if isinstance(line, dict)
    }
    merged: list[dict[str, Any]] = []
    for item in lines_out:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("poNum") or ""), str(item.get("itemNum") or ""))
        base = dict(by_key.get(key) or {})
        for field in ("lineItem", "remainingQty", "itemName", "factory"):
            if item.get(field):
                base[field] = str(item.get(field) or "").strip()
        if not base.get("poNum"):
            base["poNum"] = key[0]
        if not base.get("itemNum"):
            base["itemNum"] = key[1]
        merged.append(base)
    if merged:
        summary["lines"] = merged


async def dispatch_finished(db: AsyncSession, task: AutomationTask, run: RpaRun) -> bool:
    if task.task_type not in RPA_TEMPLATE_CODES:
        return False
    if not task.process_instance_id:
        return True
    instance = (
        await db.execute(
            select(ProcessInstance)
            .where(ProcessInstance.id == task.process_instance_id, not_deleted(ProcessInstance))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if instance is None:
        return True
    output = run.output if isinstance(run.output, dict) else {}
    summary = _summary(instance)
    succeeded = run.status == RunStatus.SUCCESS.value
    actor = task.created_by

    if task.task_type == ENRICH_TEMPLATE_CODE:
        if succeeded:
            _merge_enrich_output(summary, output)
            _save_summary(instance, summary)
            _clear_instance_error(instance)
            _change_stage(
                db, instance, ProcessStage.BOE_PACK_SAVE_DRAFT, actor=actor, note="补全行成功"
            )
            await _maybe_enqueue_rpa(
                db,
                instance,
                template_code=SAVE_DRAFT_TEMPLATE_CODE,
                title=f"保存 SRM 草稿单 - {instance.biz_key}",
                actor=actor,
                required=False,
            )
        else:
            _set_instance_error(
                instance,
                error_code=str(output.get("errorCode") or "BOE_ENRICH_FAILED"),
                error_message=str(output.get("errorMessage") or run.error_message or "补全失败"),
            )
        return True

    if task.task_type == SAVE_DRAFT_TEMPLATE_CODE:
        if isinstance(output.get("pageSnapshot"), dict):
            snap = output["pageSnapshot"]
            if isinstance(snap.get("header"), dict):
                header = dict(summary.get("header") or {})
                header.update(_editable_header(snap["header"]))
                summary["header"] = header
            if isinstance(snap.get("lines"), list):
                summary["lines"] = [
                    _editable_line(item) for item in snap["lines"] if isinstance(item, dict)
                ]
        if succeeded:
            draft_no = str(output.get("srmDraftNo") or "").strip()
            if draft_no:
                summary["srmDraftNo"] = draft_no
            summary["reviewBaseline"] = {
                "capturedAt": _now().isoformat(),
                "srmDraftNo": summary.get("srmDraftNo") or "",
                "header": {
                    key: (summary.get("header") or {}).get(key, "")
                    for key in ("invoiceNo", "factory", "invoiceDate", "etd", "consignArrivalDate", "totalVol")
                },
                "lines": summary.get("lines") or [],
            }
            _save_summary(instance, summary)
            _clear_instance_error(instance)
            _change_stage(
                db, instance, ProcessStage.BOE_PACK_REVIEW, actor=actor, note="SRM 草稿已保存"
            )
        else:
            _save_summary(instance, summary)
            _set_instance_error(
                instance,
                error_code=str(output.get("errorCode") or "BOE_SAVE_DRAFT_FAILED"),
                error_message=str(output.get("errorMessage") or run.error_message or "保存草稿失败"),
            )
        return True

    if task.task_type == SUBMIT_TEMPLATE_CODE:
        if succeeded:
            instance.status = ProcessInstanceStatus.COMPLETED.value
            _clear_instance_error(instance)
            _change_stage(
                db, instance, ProcessStage.BOE_PACK_SUBMITTED, actor=actor, note="已提交 SRM"
            )
        else:
            _change_stage(
                db, instance, ProcessStage.BOE_PACK_REVIEW, actor=actor, note="提交失败"
            )
            _set_instance_error(
                instance,
                error_code=str(output.get("errorCode") or "BOE_SUBMIT_FAILED"),
                error_message=str(output.get("errorMessage") or run.error_message or "提交失败"),
            )
        _save_summary(instance, summary)
        return True
    return True
