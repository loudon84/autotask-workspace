"""京东方发票箱单 SOP constants."""

from app.models.enums import ProcessStage

# @lat: [[domain#BoeInvoicePacking]]
PROCESS_CODE = "srm_boe_invoice_packing"

VOL_UNIT = "立方米"
NET_WEIGHT_UNIT = "千克"
EXPECTED_ORG_CODE = "101"

ENRICH_TEMPLATE_CODE = "srm_boe_pack_enrich"
SAVE_DRAFT_TEMPLATE_CODE = "srm_boe_pack_save_draft"
SUBMIT_TEMPLATE_CODE = "srm_boe_pack_submit"
DELETE_DRAFT_TEMPLATE_CODE = "srm_boe_pack_delete_draft"

RPA_TEMPLATE_CODES = frozenset(
    {
        ENRICH_TEMPLATE_CODE,
        SAVE_DRAFT_TEMPLATE_CODE,
        SUBMIT_TEMPLATE_CODE,
        DELETE_DRAFT_TEMPLATE_CODE,
    }
)

IN_FLIGHT_TASK_STATUSES = frozenset({"QUEUED", "LEASED", "RUNNING", "WAITING_HUMAN"})
BUSY_LEASE_STATUSES = frozenset({"LEASED", "RUNNING", "WAITING_HUMAN"})

MAIN_STAGES = [
    ProcessStage.BOE_PACK_SCAN_PLAN.value,
    ProcessStage.BOE_PACK_FETCH_WMS.value,
    ProcessStage.BOE_PACK_ENRICH.value,
    ProcessStage.BOE_PACK_SAVE_DRAFT.value,
    ProcessStage.BOE_PACK_REVIEW.value,
    ProcessStage.BOE_PACK_SUBMITTING.value,
    ProcessStage.BOE_PACK_SUBMITTED.value,
]

STAGE_DEFINITIONS = [
    {"id": ProcessStage.BOE_PACK_SCAN_PLAN.value, "name": "匹配交货计划", "button": None},
    {"id": ProcessStage.BOE_PACK_FETCH_WMS.value, "name": "读 WMS 装箱单", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_ENRICH.value, "name": "RPA 补全项目信息行", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_SAVE_DRAFT.value, "name": "保存 SRM 草稿单", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_REVIEW.value, "name": "客服核验", "button": "提交"},
    {"id": ProcessStage.BOE_PACK_SUBMITTING.value, "name": "提交 SRM 单据", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_SUBMITTED.value, "name": "已完成", "button": None},
    {"id": ProcessStage.BOE_PACK_DELETING_DRAFT.value, "name": "删除 SRM 草稿", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_CANCELLED.value, "name": "已作废", "button": None},
]

RETRYABLE_STAGES = frozenset(
    {
        ProcessStage.BOE_PACK_FETCH_WMS.value,
        ProcessStage.BOE_PACK_ENRICH.value,
        ProcessStage.BOE_PACK_SAVE_DRAFT.value,
        ProcessStage.BOE_PACK_SUBMITTING.value,
        ProcessStage.BOE_PACK_DELETING_DRAFT.value,
    }
)

EDITABLE_STAGES = frozenset(
    {
        ProcessStage.BOE_PACK_REVIEW.value,
        ProcessStage.BOE_PACK_SAVE_DRAFT.value,
    }
)

REQUIRED_HEADER_FIELDS = (
    ("invoiceNo", "供应商发票号"),
    ("factory", "BOE 工厂"),
    ("invoiceDate", "开票日期"),
    ("etd", "ETD"),
    ("consignArrivalDate", "委托到货日期"),
    ("totalVol", "总体积"),
)
REQUIRED_LINE_FIELDS = (
    ("deliveryQty", "本次开票数"),
    ("netWeight", "净重"),
    ("regionSrmName", "SRM 地区"),
)

ATTACH_TYPE_PACKING = "箱单"
ATTACH_TYPE_INVOICE = "发票"
ATTACH_TYPE_BL = "提运单"
ATTACH_TYPE_DUAL = "双签PO/协议"
ATTACH_TYPES = (
    ATTACH_TYPE_PACKING,
    ATTACH_TYPE_INVOICE,
    ATTACH_TYPE_BL,
    ATTACH_TYPE_DUAL,
)
ATTACH_PDF_SUFFIXES = {".pdf"}


def _text(value: object) -> str:
    return str(value or "").strip()


def unmapped_region_codes(lines: list, maps: dict[str, str]) -> list[str]:
    """WMS 地区编号必须在对照表里有 SRM 显示名，否则不能进补全。"""
    missing: list[str] = []
    seen: set[str] = set()
    for line in lines or []:
        if not isinstance(line, dict):
            continue
        code = _text(line.get("regionCode"))
        name = (maps.get(code) or "").strip() if code else ""
        if name:
            continue
        label = code or "(空)"
        if label in seen:
            continue
        seen.add(label)
        missing.append(label)
    return missing


def _file_stem(name: str) -> str:
    text = _text(name)
    if "." in text:
        return text.rsplit(".", 1)[0].strip()
    return text


def review_required_errors(header: dict, lines: list) -> list[str]:
    """客服核验可填字段全部必填。"""
    errors: list[str] = []
    for key, label in REQUIRED_HEADER_FIELDS:
        if not _text((header or {}).get(key)):
            errors.append(f"{label}不能为空")
    if not lines:
        errors.append("项目信息至少一行")
        return errors
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            continue
        for key, label in REQUIRED_LINE_FIELDS:
            if not _text(line.get(key)):
                errors.append(f"第 {index} 行{label}不能为空")
    return errors


def normalize_attachments(raw: list) -> list[dict]:
    rows: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        attach_type = _text(item.get("type") or item.get("fileType"))
        if attach_type == "提单":
            attach_type = ATTACH_TYPE_BL
        rows.append(
            {
                "id": _text(item.get("id")) or f"att-{len(rows)+1}",
                "type": attach_type,
                "fileName": _text(item.get("fileName") or item.get("name")),
                "filePath": _text(item.get("filePath") or item.get("path")),
            }
        )
    return rows


def attachment_rule_errors(invoice_no: str, lines: list, attachments: list) -> list[str]:
    """箱单文件名须含 pl（大小写不限）；发票按发票号命名；提运单不限；双签=唯一 PO。"""
    invoice = _text(invoice_no)
    rows = normalize_attachments(attachments)
    errors: list[str] = []
    if not invoice:
        errors.append("供应商发票号不能为空，无法校验附件命名")
        return errors
    pos = sorted(
        {
            _text(line.get("poNum"))
            for line in (lines or [])
            if isinstance(line, dict) and _text(line.get("poNum"))
        }
    )
    by_type: dict[str, list[dict]] = {key: [] for key in ATTACH_TYPES}
    for row in rows:
        kind = row["type"]
        if kind not in by_type:
            errors.append(f"不支持的附件类型：{kind or '空'}")
            continue
        if not row["fileName"]:
            if kind == ATTACH_TYPE_BL:
                continue
            errors.append(f"{kind or '附件'}未选择文件")
            continue
        suffix = ""
        if "." in row["fileName"]:
            suffix = "." + row["fileName"].rsplit(".", 1)[-1].lower()
        if suffix not in ATTACH_PDF_SUFFIXES:
            errors.append(f"{row['fileName']} 必须是 PDF")
            continue
        by_type[kind].append(row)

    packing_rows = by_type[ATTACH_TYPE_PACKING]
    if not packing_rows:
        errors.append("必须上传箱单")
    for row in packing_rows:
        if "pl" not in row["fileName"].lower():
            errors.append("箱单文件名须包含 pl（大小写均可）")

    invoice_rows = by_type[ATTACH_TYPE_INVOICE]
    if not invoice_rows:
        errors.append("必须上传发票")
    for row in invoice_rows:
        if _file_stem(row["fileName"]).lower() != invoice.lower():
            errors.append(f"发票文件名必须是 {invoice}.pdf")

    dual_rows = by_type[ATTACH_TYPE_DUAL]
    if len(dual_rows) != len(pos):
        errors.append(f"双签PO/协议须与交货明细 PO 数量一致（需要 {len(pos)} 个）")
    covered: set[str] = set()
    for row in dual_rows:
        stem = _file_stem(row["fileName"])
        if stem not in pos:
            errors.append(f"双签文件名必须是采购订单号，未匹配：{row['fileName']}")
            continue
        if stem in covered:
            errors.append(f"双签 PO {stem} 重复上传")
            continue
        covered.add(stem)
    missing = [po for po in pos if po not in covered]
    if missing:
        errors.append("缺少双签PO：" + "、".join(missing))
    return errors
