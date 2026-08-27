import asyncio
import io
import re
import zipfile
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

import httpx
from nodeskclaw_rpa_engine.runtime import (
    login_official_srm,
    RpaBusinessError,
    RpaFatalError,
    RpaHumanRequiredError,
    RpaRetryableError,
)

CAPTCHA_CODES = {
    "code01": "mp3s",
    "code02": "0ada",
    "code03": "sez0",
    "code04": "ggmh",
    "code05": "rpyt",
    "code06": "y5na",
    "code07": "elhx",
    "code08": "el0m",
    "code09": "aqh9",
    "code10": "gqcy",
}
PO_NUMBER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
MAX_XLSX_BYTES = 10 * 1024 * 1024
MAX_XLSX_FILES = 100
MAX_XLSX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
ERP_TEXT_LIMIT = 240
DEFAULT_ORDER_TYPE = "常规订单"
DEFAULT_TAX_RATE = Decimal("0.13")
CHINA_TIMEZONE = timezone(timedelta(hours=8))

ERP_TOKEN_PATH = "/core/oauth/token"
ERP_ORDER_IMPORT_PATH = "/core/api/srm/so/salesOrderImport"
ERP_CLIENT_ID_PLACEHOLDER = "__FILL_ERP_CLIENT_ID__"
ERP_CLIENT_SECRET_PLACEHOLDER = "__FILL_ERP_CLIENT_SECRET__"
ERP_TOKEN_TIMEOUT_SECONDS = 15.0
ERP_IMPORT_TIMEOUT_SECONDS = 60.0
ERP_PROCESS_MESSAGE_LIMIT = 500
OUTPUT_SCHEMA_VERSION = "ORDER_DOWNLOAD_PUSH_OUTPUT_V1"

_CLICK_VISIBLE_DETAIL_JS = r"""(poNo) => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const isVisible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return false;
    const style = window.getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) {
      return false;
    }
    return true;
  };
  const findDetail = (row) => [...row.querySelectorAll('button, a, .el-button, .el-link, span')].find((el) => {
    const text = clean(el.innerText);
    return (text === '详情' || text === '查看') && isVisible(el);
  });
  const mainBodies = [...document.querySelectorAll('.el-table__body-wrapper tbody')].filter(
    (body) => !body.closest('.el-table__fixed-right, .el-table__fixed')
  );
  let index = -1;
  for (const body of mainBodies) {
    const rows = [...body.querySelectorAll(':scope > tr')];
    index = rows.findIndex((row) => clean(row.innerText).includes(poNo));
    if (index >= 0) break;
  }
  if (index < 0) return false;
  const rowsToTry = [];
  const fixedBody = document.querySelector(
    '.el-table__fixed-right .el-table__body-wrapper tbody'
  );
  if (fixedBody) {
    const fixedRow = fixedBody.querySelectorAll(':scope > tr')[index];
    if (fixedRow) rowsToTry.push(fixedRow);
  }
  for (const body of mainBodies) {
    const row = body.querySelectorAll(':scope > tr')[index];
    if (row) rowsToTry.push(row);
  }
  for (const row of rowsToTry) {
    const btn = findDetail(row);
    if (btn) {
      const target = btn.closest('button, a, .el-button, .el-link') || btn;
      target.click();
      return true;
    }
  }
  return false;
}"""

ERP_RESULT_ROW_FIELDS = (
    "orderNumber",
    "sourceHeaderId",
    "headerId",
    "soStatus",
    "soApprovedStatus",
    "processGroupId",
    "processStatusCode",
    "processMessage",
)

XLSX_REQUIRED_HEADERS = {
    "供应商编号",
    "供应商名称",
    "订单编号",
    "订单行号",
    "料号",
    "料品名称",
    "料品规格",
    "数量",
    "单位",
    "单价（元）",
    "价税合计（元）",
    "要求交货日期",
}

ATTACHMENT_FIELD_MAP = {
    "供应商编号": "supplierCode",
    "供应商名称": "supplierName",
    "订单编号": "poNo",
    "订单行号": "lineNumber",
    "料号": "customerItemNumber",
    "料品名称": "itemName",
    "料品规格": "itemSpecification",
    "物料状态": "materialStatus",
    "内码": "internalCode",
    "数量": "orderQuantity",
    "单位": "orderQuantityUom",
    "单价（元）": "unitSellingPrice",
    "价税合计（元）": "taxIncludedAmount",
    "要求交货日期": "requestDate",
    "标准交货日期（天）": "standardDeliveryDays",
    "是否满足LT": "meetsLeadTime",
    "供方交期": "supplierDeliveryDate",
    "欠交数量": "outstandingQuantity",
    "备注": "remarks",
    "直发备注": "directShipmentRemarks",
}


def resolve_captcha_code(image_src):
    if not isinstance(image_src, str) or not image_src.strip():
        return None
    clean_src = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean_src.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _ctx_text(ctx, *keys):
    sources = (_mapping(getattr(ctx, "config", None)), _mapping(getattr(ctx, "credentials", None)))
    for key in keys:
        for source in sources:
            text = str(source.get(key) or "").strip()
            if text:
                return text
    return ""


def _join_url(base, path):
    return f"{str(base).strip().rstrip('/')}/{str(path).lstrip('/')}"


def _require_erp_base(ctx):
    base = _ctx_text(ctx, "erpBaseUrl")
    if not base:
        raise RpaFatalError(
            "ERP_ENDPOINT_NOT_CONFIGURED",
            "ERP base URL is not configured",
        )
    return base


def _customer_name_from_ctx(ctx):
    name = _ctx_text(ctx, "customerName")
    if not name:
        raise RpaBusinessError(
            "ERP_REQUIRED_FIELD_MISSING",
            "ERP order header is missing a required field",
        )
    return name


def _org_name_from_ctx(ctx):
    name = _ctx_text(ctx, "businessEntity")
    if not name:
        raise RpaBusinessError(
            "ERP_REQUIRED_FIELD_MISSING",
            "ERP order header is missing orgName (portal businessEntity)",
        )
    return name


def _customer_sub_code_from_ctx(ctx):
    code = _ctx_text(ctx, "customerCode")
    if not code:
        raise RpaBusinessError(
            "ERP_REQUIRED_FIELD_MISSING",
            "ERP order header is missing customerSubCode (portal erpEntityCode)",
        )
    return code


def _org_code_from_ctx(ctx):
    code = _ctx_text(ctx, "ou")
    if not code:
        raise RpaBusinessError(
            "ERP_REQUIRED_FIELD_MISSING",
            "ERP order header is missing orgCode (portal ou)",
        )
    return code


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _erp_text(value, field_name):
    text = _clean(value)
    if len(text) > ERP_TEXT_LIMIT:
        raise RpaBusinessError(
            "ERP_FIELD_TOO_LONG",
            f"ERP field exceeds 240 characters: {field_name}",
        )
    return text


def _decimal(value, field_name):
    text = _clean(value).replace(",", "")
    if not text:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INCOMPLETE",
            f"Required numeric field is missing: {field_name}",
        )
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INVALID",
            f"Numeric field is invalid: {field_name}",
        ) from exc
    if not result.is_finite():
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INVALID",
            f"Numeric field is invalid: {field_name}",
        )
    return result


def _json_number(value):
    return int(value) if value == value.to_integral_value() else float(value)


def _column_index(cell_ref):
    value = 0
    for char in str(cell_ref):
        if not char.isalpha():
            break
        value = value * 26 + ord(char.upper()) - 64
    return value - 1


def _xlsx_target(target):
    raw = target.replace("\\", "/").lstrip("/")
    path = PurePosixPath(raw if raw.startswith("xl/") else f"xl/{raw}")
    if ".." in path.parts:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_INVALID",
            "Order attachment contains an unsafe worksheet path",
        )
    return path.as_posix()


def parse_order_xlsx(content):
    if not isinstance(content, bytes) or not content.startswith(b"PK\x03\x04"):
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_INVALID",
            "Downloaded order attachment is not a valid XLSX file",
        )
    if len(content) > MAX_XLSX_BYTES:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_TOO_LARGE",
            "Downloaded order attachment exceeds the Flow size limit",
        )
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    office_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    ns = {"m": main_ns, "r": office_ns, "p": package_ns}
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_XLSX_FILES:
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_INVALID",
                    "Order attachment contains too many files",
                )
            if sum(item.file_size for item in infos) > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_INVALID",
                    "Order attachment expands beyond the Flow size limit",
                )
            names = set(archive.namelist())
            required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            if not required.issubset(names):
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_INVALID",
                    "Order attachment workbook metadata is missing",
                )
            shared = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                for item in root.findall("m:si", ns):
                    shared.append(
                        "".join(
                            node.text or "" for node in item.iter(f"{{{main_ns}}}t")
                        )
                    )
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            targets = {
                item.attrib["Id"]: item.attrib["Target"]
                for item in relations.findall("p:Relationship", ns)
            }
            sheets = workbook.find("m:sheets", ns)
            if sheets is None or not list(sheets):
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_INVALID",
                    "Order attachment does not contain a worksheet",
                )
            sheet = list(sheets)[0]
            target = _xlsx_target(targets[sheet.attrib[f"{{{office_ns}}}id"]])
            if target not in names:
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_INVALID",
                    "Order attachment worksheet is missing",
                )
            worksheet = ET.fromstring(archive.read(target))
            rows = []
            for row in worksheet.findall(".//m:sheetData/m:row", ns):
                values = []
                for cell in row.findall("m:c", ns):
                    index = _column_index(cell.attrib.get("r", "A1"))
                    while len(values) <= index:
                        values.append("")
                    kind = cell.attrib.get("t")
                    value = cell.find("m:v", ns)
                    inline = cell.find("m:is", ns)
                    if kind == "inlineStr" and inline is not None:
                        parsed = "".join(
                            node.text or "" for node in inline.iter(f"{{{main_ns}}}t")
                        )
                    elif value is None or value.text is None:
                        parsed = ""
                    elif kind == "s":
                        parsed = shared[int(value.text)]
                    elif kind == "b":
                        parsed = "true" if value.text == "1" else "false"
                    else:
                        parsed = value.text
                    values[index] = _clean(parsed)
                while values and not values[-1]:
                    values.pop()
                if any(values):
                    rows.append(values)
    except RpaBusinessError:
        raise
    except (
        KeyError,
        IndexError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
        ET.ParseError,
    ) as exc:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_INVALID",
            "Downloaded order attachment could not be parsed",
        ) from exc
    if len(rows) < 2:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INCOMPLETE",
            "Order attachment does not contain order lines",
        )
    headers = [_clean(value) for value in rows[0]]
    if len(headers) != len(set(headers)):
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INVALID",
            "Order attachment contains duplicate column names",
        )
    missing = sorted(XLSX_REQUIRED_HEADERS.difference(headers))
    if missing:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INCOMPLETE",
            f"Order attachment columns are missing: {', '.join(missing)}",
        )
    records = []
    for values in rows[1:]:
        raw = {
            header: values[index] if index < len(values) else ""
            for index, header in enumerate(headers)
        }
        if not any(raw.values()):
            continue
        records.append(
            {
                target: raw.get(source, "")
                for source, target in ATTACHMENT_FIELD_MAP.items()
            }
        )
    if not records:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INCOMPLETE",
            "Order attachment does not contain order lines",
        )
    suppliers = {
        (_clean(item["supplierCode"]), _clean(item["supplierName"])) for item in records
    }
    if len(suppliers) != 1:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INVALID",
            "Order attachment contains inconsistent supplier identities",
        )
    return {
        "sheetName": _clean(sheet.attrib.get("name")),
        "supplierCode": records[0]["supplierCode"],
        "supplierName": records[0]["supplierName"],
        "lines": records,
    }


def reconcile_attachment_with_portal(po_no, portal_lines, attachment):
    normalized_po_no = _clean(po_no).upper()
    if not PO_NUMBER_PATTERN.fullmatch(normalized_po_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Customer purchase order number is missing or invalid",
        )
    if not isinstance(portal_lines, list) or not portal_lines:
        raise RpaBusinessError(
            "ORDER_DETAIL_LINES_UNAVAILABLE",
            "Customer purchase order detail lines are unavailable",
        )

    ordered_portal_identities = []
    portal_by_line_number = {}
    for index, raw_line in enumerate(portal_lines):
        if not isinstance(raw_line, Mapping):
            raise RpaBusinessError(
                "ORDER_DETAIL_LINES_UNAVAILABLE",
                "Customer purchase order detail line identity is invalid",
                details={"index": index},
            )
        line_number = _clean(raw_line.get("lineNumber"))
        customer_item_number = _clean(raw_line.get("customerItemNumber"))
        if not line_number or not customer_item_number:
            raise RpaBusinessError(
                "ORDER_DETAIL_LINES_UNAVAILABLE",
                "Customer purchase order detail line identity is incomplete",
                details={"index": index},
            )
        if line_number in portal_by_line_number:
            raise RpaBusinessError(
                "ORDER_DETAIL_LINE_DUPLICATE",
                "Customer purchase order detail contains a duplicate line number",
                details={"lineNumber": line_number},
            )
        identity = (line_number, customer_item_number)
        portal_by_line_number[line_number] = identity
        ordered_portal_identities.append(identity)

    attachment_lines = (
        attachment.get("lines") if isinstance(attachment, Mapping) else None
    )
    if not isinstance(attachment_lines, list) or not attachment_lines:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_LINE_COUNT_MISMATCH",
            "Order attachment line count does not match the portal detail",
            details={
                "portalLineCount": len(ordered_portal_identities),
                "attachmentLineCount": 0,
            },
        )

    attachment_by_line_number = {}
    attachment_by_identity = {}
    for index, raw_line in enumerate(attachment_lines):
        if not isinstance(raw_line, Mapping):
            raise RpaBusinessError(
                "ORDER_ATTACHMENT_LINE_MISMATCH",
                "Order attachment line identity is invalid",
                details={"index": index},
            )
        line_number = _clean(raw_line.get("lineNumber"))
        customer_item_number = _clean(raw_line.get("customerItemNumber"))
        if not line_number or not customer_item_number:
            raise RpaBusinessError(
                "ORDER_ATTACHMENT_LINE_MISMATCH",
                "Order attachment line identity is incomplete",
                details={"index": index},
            )
        if line_number in attachment_by_line_number:
            raise RpaBusinessError(
                "ORDER_ATTACHMENT_LINE_DUPLICATE",
                "Order attachment contains a duplicate line number",
                details={"lineNumber": line_number},
            )
        identity = (line_number, customer_item_number)
        attachment_by_line_number[line_number] = identity
        attachment_by_identity[identity] = raw_line

    if len(ordered_portal_identities) != len(attachment_lines):
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_LINE_COUNT_MISMATCH",
            "Order attachment line count does not match the portal detail",
            details={
                "portalLineCount": len(ordered_portal_identities),
                "attachmentLineCount": len(attachment_lines),
            },
        )

    portal_identity_set = set(ordered_portal_identities)
    attachment_identity_set = set(attachment_by_identity)
    if portal_identity_set != attachment_identity_set:
        missing = sorted(portal_identity_set - attachment_identity_set)
        unexpected = sorted(attachment_identity_set - portal_identity_set)
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_LINE_MISMATCH",
            "Order attachment line identities do not match the portal detail",
            details={
                "missingFromAttachment": [
                    {
                        "lineNumber": line_number,
                        "customerItemNumber": customer_item_number,
                    }
                    for line_number, customer_item_number in missing
                ],
                "unexpectedInAttachment": [
                    {
                        "lineNumber": line_number,
                        "customerItemNumber": customer_item_number,
                    }
                    for line_number, customer_item_number in unexpected
                ],
            },
        )

    normalized_lines = []
    normalized_po_number_count = 0
    for identity in ordered_portal_identities:
        source_line = attachment_by_identity[identity]
        normalized_line = dict(source_line)
        if _clean(normalized_line.get("poNo")) != normalized_po_no:
            normalized_po_number_count += 1
        normalized_line["poNo"] = normalized_po_no
        normalized_lines.append(normalized_line)

    normalized_attachment = dict(attachment)
    normalized_attachment["lines"] = normalized_lines
    return normalized_attachment, {
        "portalLineCount": len(ordered_portal_identities),
        "attachmentLineCount": len(attachment_lines),
        "normalizedPoNumberCount": normalized_po_number_count,
    }


def _attachment_comments(lines):
    comments = []
    for line in lines:
        value = _clean(line.get("remarks"))
        if value and value not in comments:
            comments.append(value)
    return "；".join(comments)


def build_erp_draft(
    po_no,
    attachment,
    ordered_date=None,
    customer_name=None,
    org_name=None,
    customer_sub_code=None,
    org_code=None,
):
    resolved_ordered_date = _clean(
        ordered_date or datetime.now(CHINA_TIMEZONE).date().isoformat()
    )
    erp_lines = []
    resolved_lines = []
    for line in attachment["lines"]:
        line_no = _clean(line["lineNumber"])
        item_no = _clean(line["customerItemNumber"])
        quantity = _decimal(line["orderQuantity"], "orderQuantity")
        selling_price = _decimal(line["unitSellingPrice"], "unitSellingPrice")
        untaxed = (selling_price / (Decimal("1") + DEFAULT_TAX_RATE)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        erp_line = {
            "lineNumber": "",
            "lineType": "",
            "custPoLine": _erp_text(line_no, "custPoLine"),
            "custPoNumber": _erp_text(line["poNo"], "custPoNumber"),
            "custItemNum": _erp_text(item_no, "custItemNum"),
            "itemNumber": "",
            "itemDescription": "",
            "orderQuantity": _json_number(quantity),
            "orderQuantityUom": "",
            "unitSellingPrice": _json_number(selling_price),
            "unTaxPrice": format(untaxed, "f"),
            "priceListName": "",
            "requestDate": _erp_text(line["requestDate"], "requestDate"),
            "factoryLocation": "",
            "customerJob": "",
            "productLine": "",
            "pm": "",
            "usdPrice": "",
            "deliveryRate": "",
            "actualExchangeRate": "",
            "sourceLineId": "",
        }
        erp_lines.append(erp_line)
        resolved_lines.append(
            {
                **line,
                "taxRate": format(DEFAULT_TAX_RATE, "f"),
                "unTaxPrice": format(untaxed, "f"),
            }
        )
    header = {
        "orderNumber": "",
        "customerNumber": "",
        "customerName": _erp_text(customer_name, "customerName"),
        "customerSubCode": _erp_text(customer_sub_code, "customerSubCode"),
        "salesrep": "",
        "invoiceToLocation": "",
        "orderType": DEFAULT_ORDER_TYPE,
        "orderedDate": _erp_text(resolved_ordered_date, "orderedDate"),
        "currencyCode": "",
        "orgCode": _erp_text(org_code, "orgCode"),
        "orgName": _erp_text(org_name, "orgName"),
        "priceListName": "",
        "fobPointCode": "",
        "paymentTerm": "",
        "comments": _erp_text(_attachment_comments(attachment["lines"]), "comments"),
        "fob": "",
        "userNo": "",
        "isAttachment": "Y",
        "sourceHeaderId": "",
        "lines": erp_lines,
    }
    required_header = (
        "customerName",
        "customerSubCode",
        "orderType",
        "orderedDate",
        "orgCode",
        "orgName",
        "isAttachment",
    )
    required_line = (
        "custPoLine",
        "custPoNumber",
        "custItemNum",
        "orderQuantity",
        "unitSellingPrice",
        "requestDate",
    )
    if any(header.get(name) in (None, "") for name in required_header):
        raise RpaBusinessError(
            "ERP_REQUIRED_FIELD_MISSING",
            "ERP order header is missing a required field",
        )
    if any(
        any(line.get(name) in (None, "") for name in required_line)
        for line in erp_lines
    ):
        raise RpaBusinessError(
            "ERP_REQUIRED_FIELD_MISSING",
            "ERP order line is missing a required field",
        )
    return [header], resolved_lines


def _erp_credentials(client_id, client_secret):
    resolved_client_id = str(client_id or "").strip()
    resolved_client_secret = str(client_secret or "")
    if (
        not resolved_client_id
        or not resolved_client_secret.strip()
        or resolved_client_id == ERP_CLIENT_ID_PLACEHOLDER
        or resolved_client_secret == ERP_CLIENT_SECRET_PLACEHOLDER
    ):
        raise RpaFatalError(
            "ERP_CREDENTIALS_NOT_CONFIGURED",
            "ERP OAuth client credentials are not configured",
        )
    return resolved_client_id, resolved_client_secret


def _response_object(response):
    try:
        value = response.json()
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _safe_erp_row_value(field, value):
    if value is None:
        return None
    limit = ERP_PROCESS_MESSAGE_LIMIT if field == "processMessage" else ERP_TEXT_LIMIT
    return _clean(value)[:limit]


def _safe_erp_result(value):
    rows = value.get("rows")
    total = value.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        total = None
    safe_rows = []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                safe_rows.append(
                    {
                        field: _safe_erp_row_value(field, row.get(field))
                        for field in ERP_RESULT_ROW_FIELDS
                    }
                )
    return {
        "code": _clean(value.get("code")),
        "message": _clean(value.get("message"))[:ERP_TEXT_LIMIT],
        "success": value.get("success") is True,
        "total": total,
        "rows": safe_rows,
    }


def _build_order_summary(po_no, draft):
    order_detail = draft.get("orderDetail") if isinstance(draft, dict) else None
    if not isinstance(order_detail, dict):
        raise RpaFatalError(
            "ERP_SUCCESS_OUTPUT_INVALID",
            "ERP order summary is unavailable",
        )
    raw_lines = order_detail.get("lines")
    if (
        not isinstance(raw_lines, list)
        or not raw_lines
        or any(not isinstance(line, dict) for line in raw_lines)
    ):
        raise RpaFatalError(
            "ERP_SUCCESS_OUTPUT_INVALID",
            "ERP order line summary is unavailable",
        )
    supplier_name = _clean(order_detail.get("supplierName"))
    if not supplier_name:
        raise RpaFatalError(
            "ERP_SUCCESS_OUTPUT_INVALID",
            "ERP supplier summary is unavailable",
        )
    return {
        "poNo": _clean(po_no).upper(),
        "supplierCode": _clean(order_detail.get("supplierCode")),
        "supplierName": supplier_name,
        "lineCount": len(raw_lines),
        "lines": [dict(line) for line in raw_lines],
    }


def _erp_order_number(erp_result):
    rows = erp_result.get("rows") if isinstance(erp_result, dict) else None
    order_numbers = []
    if isinstance(rows, list):
        for row in rows:
            order_number = _clean(
                row.get("orderNumber") if isinstance(row, dict) else None
            )
            if order_number and order_number not in order_numbers:
                order_numbers.append(order_number)
    if len(order_numbers) != 1:
        raise RpaHumanRequiredError(
            "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
            "ERP sales order number requires manual verification",
            details={"rows": rows if isinstance(rows, list) else []},
        )
    return order_numbers[0]


def _erp_header_id(erp_result):
    """从 ERP 成功 rows 取首个非空 headerId（用于 SDMS 查看页 fdId）。"""
    rows = erp_result.get("rows") if isinstance(erp_result, dict) else None
    if not isinstance(rows, list):
        return ""
    for row in rows:
        if not isinstance(row, dict):
            continue
        header_id = _clean(row.get("headerId"))
        if header_id:
            return header_id
    return ""


async def _emit_erp_event_safely(
    ctx,
    event_type,
    *,
    level="INFO",
    message,
    payload=None,
):
    try:
        await ctx.events.emit(
            event_type,
            level=level,
            message=message,
            payload=payload,
        )
    except Exception:
        # ERP may already have committed the order. Event delivery must never
        # turn a completed import into a whole-Flow retry and duplicate order.
        return


class ErpSalesOrderClient:
    def __init__(
        self,
        *,
        token_url,
        import_url,
        client_id,
        client_secret,
        http_client,
    ):
        self.token_url = token_url
        self.import_url = import_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.http = http_client

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        # 共享 ctx.http，这里不能 close。不要 del exc 后再读，否则会把
        # ERP_ORDER_IMPORT_ROW_FAILED 变成 NameError / FLOW_UNHANDLED_ERROR。
        if isinstance(exc, asyncio.CancelledError):
            raise RpaHumanRequiredError(
                "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                "ERP sales order submission requires manual verification",
            ) from None

    async def fetch_access_token(self):
        client_id, client_secret = _erp_credentials(
            self.client_id,
            self.client_secret,
        )
        try:
            response = await self.http.post(
                self.token_url,
                system="ERP",
                params={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
                timeout=ERP_TOKEN_TIMEOUT_SECONDS,
            )
        except httpx.RequestError:
            raise RpaRetryableError(
                "ERP_TOKEN_REQUEST_FAILED",
                "ERP access token could not be requested",
            ) from None

        if 300 <= response.status_code < 400:
            raise RpaFatalError(
                "ERP_TOKEN_REDIRECT_REJECTED",
                "ERP token endpoint returned an unsupported redirect",
            )
        if response.status_code == 429 or response.status_code >= 500:
            raise RpaRetryableError(
                "ERP_TOKEN_SERVICE_UNAVAILABLE",
                "ERP token service is temporarily unavailable",
            )
        if not 200 <= response.status_code < 300:
            raise RpaFatalError(
                "ERP_TOKEN_REJECTED",
                "ERP token service rejected the configured client",
            )

        value = _response_object(response)
        if value is None:
            raise RpaFatalError(
                "ERP_TOKEN_RESPONSE_INVALID",
                "ERP token service returned an invalid response",
            )
        raw_access_token = value.get("access_token")
        raw_token_type = value.get("token_type")
        access_token = (
            raw_access_token.strip() if isinstance(raw_access_token, str) else ""
        )
        token_type = (
            raw_token_type.strip().casefold() if isinstance(raw_token_type, str) else ""
        )
        if not access_token or token_type != "bearer":
            raise RpaFatalError(
                "ERP_TOKEN_RESPONSE_INVALID",
                "ERP token service returned an invalid response",
            )
        return token_type, access_token

    async def import_sales_order(self, payload, token_type, access_token):
        if not isinstance(payload, list) or not payload:
            raise RpaFatalError(
                "ERP_ORDER_PAYLOAD_INVALID",
                "ERP sales order payload is unavailable",
            )
        try:
            response = await self.http.post(
                self.import_url,
                system="ERP",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"{token_type} {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=ERP_IMPORT_TIMEOUT_SECONDS,
            )
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.PoolTimeout,
        ):
            raise RpaRetryableError(
                "ERP_ORDER_IMPORT_CONNECTION_FAILED",
                "ERP sales order endpoint could not be reached",
            ) from None
        except httpx.RequestError:
            raise RpaHumanRequiredError(
                "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                "ERP sales order submission requires manual verification",
            ) from None

        value = _response_object(response)
        if (
            isinstance(value, dict)
            and _clean(value.get("error")).casefold() == "invalid_token"
        ):
            raise RpaFatalError(
                "ERP_ACCESS_TOKEN_INVALID",
                "ERP sales order endpoint rejected the access token",
            )
        if response.status_code in {401, 403}:
            raise RpaFatalError(
                "ERP_ACCESS_TOKEN_INVALID",
                "ERP sales order endpoint rejected the access token",
            )
        if response.status_code in {404, 405, 415}:
            raise RpaFatalError(
                "ERP_ORDER_IMPORT_ENDPOINT_INVALID",
                "ERP sales order endpoint configuration is invalid",
            )
        if 300 <= response.status_code < 400:
            raise RpaFatalError(
                "ERP_ORDER_IMPORT_REDIRECT_REJECTED",
                "ERP sales order endpoint returned an unsupported redirect",
            )
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise RpaHumanRequiredError(
                "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                "ERP sales order submission requires manual verification",
            )
        if not 200 <= response.status_code < 300:
            raise RpaBusinessError(
                "ERP_ORDER_IMPORT_REJECTED",
                "ERP rejected the sales order import request",
            )
        if value is None:
            raise RpaHumanRequiredError(
                "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                "ERP sales order submission requires manual verification",
            )

        code = _clean(value.get("code"))
        success = value.get("success")
        if code == "2001" and success is False:
            raise RpaBusinessError(
                "ERP_ORDER_IMPORT_REJECTED",
                "ERP rejected the sales order import request",
            )
        if code != "2000" or success is not True:
            raise RpaHumanRequiredError(
                "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                "ERP sales order submission requires manual verification",
            )
        safe_result = _safe_erp_result(value)
        raw_rows = value.get("rows")
        safe_rows = safe_result["rows"]
        if (
            not isinstance(raw_rows, list)
            or not raw_rows
            or len(safe_rows) != len(raw_rows)
        ):
            raise RpaHumanRequiredError(
                "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                "ERP sales order submission requires manual verification",
                details={"rows": safe_rows},
            )

        failed_rows = [
            row
            for row in safe_rows
            if _clean(row.get("processStatusCode")).upper() == "ERROR"
        ]
        if failed_rows:
            reason = next(
                (
                    row["processMessage"]
                    for row in failed_rows
                    if isinstance(row.get("processMessage"), str)
                    and row["processMessage"]
                ),
                "ERP rejected one or more sales order rows",
            )
            raise RpaBusinessError(
                "ERP_ORDER_IMPORT_ROW_FAILED",
                reason,
                details={"rows": failed_rows},
            )

        if any(
            _clean(row.get("processStatusCode")).upper() != "COMPLETE"
            or not _clean(row.get("orderNumber"))
            for row in safe_rows
        ):
            raise RpaHumanRequiredError(
                "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                "ERP sales order submission requires manual verification",
                details={"rows": safe_rows},
            )
        return safe_result


class SupplierPortalAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.page
        self.selectors = ctx.selectors

    def selector(self, name, po_no=None):
        value = self.selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError(
                "FLOW_SELECTOR_MISSING",
                f"Required supplier portal selector is missing: {name}",
            )
        return value.replace("{po_no}", po_no) if po_no else value

    async def login(self):
        await login_official_srm(self.ctx, selector=self.selector)

    async def _wait_for_login_result(self):
        success = self.page.locator(self.selector("login_success"))
        error = self.page.locator(self.selector("login_error"))
        for _ in range(50):
            if await success.is_visible():
                return
            url = self.page.url or ""
            hash_part = url.split("#", 1)[-1] if "#" in url else ""
            if hash_part.startswith("/dashboard") or hash_part.startswith("/order"):
                return
            if await error.is_visible():
                await self._redact_login_fields()
                raise RpaBusinessError(
                    "SRM_LOGIN_FAILED",
                    "Supplier portal login failed",
                )
            await self.page.wait_for_timeout(200)
        await self._redact_login_fields()
        raise RpaRetryableError(
            "SRM_LOGIN_TIMEOUT",
            "Supplier portal login did not complete in time",
        )

    async def _redact_login_fields(self):
        for name in ("username", "password", "captcha"):
            try:
                await self.page.fill(self.selector(name), "")
            except Exception:
                continue

    async def _wait_loading_done(self):
        mask = self.selectors.get("loading_mask")
        if not isinstance(mask, str) or not mask:
            return
        try:
            await self.page.locator(mask).first.wait_for(state="hidden", timeout=15000)
        except Exception:
            return

    async def _click_visible_detail(self, po_no):
        try:
            if await self.page.evaluate(_CLICK_VISIBLE_DETAIL_JS, po_no):
                return
        except Exception:
            pass
        fixed = self.page.locator(".el-table__fixed-right").get_by_text("详情", exact=True)
        if await fixed.count():
            await fixed.first.click(timeout=8000)
            return
        await self.page.get_by_text("详情", exact=True).locator("visible=true").first.click(
            timeout=8000
        )

    async def open_order_detail(self, po_no):
        step_id = "srm.search_po"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Opening customer purchase order detail",
            payload={"stepId": step_id, "stepType": step_id},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        opened = False
        for hash_path in ("/order/list", "/supplier/orders"):
            await self.page.goto(
                f"{portal_root}/#{hash_path.lstrip('#')}",
                wait_until="domcontentloaded",
            )
            try:
                await self.page.locator(self.selector("order_page")).first.wait_for(
                    state="visible",
                    timeout=8000,
                )
                opened = True
                break
            except Exception:
                continue
        if not opened:
            raise RpaRetryableError(
                "ORDER_LIST_UNAVAILABLE",
                "Supplier portal order list could not be opened",
            )
        await self.page.fill(self.selector("po_number"), po_no)
        await self.page.click(self.selector("search_button"))
        await self._wait_loading_done()
        row = self.page.locator(self.selector("order_row", po_no))
        if await row.count() == 0:
            row = self.page.locator(".el-table__body-wrapper tbody tr").filter(has_text=po_no).first
        try:
            await row.wait_for(state="visible", timeout=10000)
        except Exception as exc:
            raise RpaBusinessError(
                "BUSINESS_NOT_FOUND",
                "Customer purchase order was not found",
            ) from exc
        try:
            await self._click_visible_detail(po_no)
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DETAIL_UNAVAILABLE",
                "Customer purchase order detail could not be opened",
            ) from exc
        await self._wait_loading_done()
        try:
            await self.page.locator(self.selector("download_order")).first.wait_for(
                state="visible",
                timeout=15000,
            )
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DETAIL_UNAVAILABLE",
                "Customer purchase order detail could not be verified",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Customer purchase order detail opened",
            payload={"stepId": step_id, "poNo": po_no},
        )

    async def collect_order_line_identities(self):
        lines_table = self.selector("lines_table")
        try:
            await self.page.locator(lines_table).first.wait_for(
                state="visible",
                timeout=10000,
            )
            raw_lines = await self.page.evaluate(
                r"""(tableSelector) => {
                  const clean = (value) =>
                    String(value || '').replace(/\s+/g, ' ').trim();
                  const tables = [...document.querySelectorAll(tableSelector)];
                  const table =
                    tables.find((candidate) =>
                      candidate.querySelector(
                        ':scope > .el-table__body-wrapper tbody tr'
                      )
                    ) || tables[0];
                  if (!table) return [];
                  const body = table.querySelector(
                    ':scope > .el-table__body-wrapper tbody'
                  );
                  if (!body) return [];
                  const headers = [
                    ...table.querySelectorAll(
                      ':scope > .el-table__header-wrapper th'
                    ),
                  ].map((header) => clean(header.textContent));
                  const lineHeaderNames = ['行号', '序号'];
                  const itemHeaderNames = ['客户料号', '物料编码', '客户物料编码'];
                  let lineIndex = headers.findIndex((header) =>
                    lineHeaderNames.some((name) => header.includes(name))
                  );
                  let itemIndex = headers.findIndex((header) =>
                    itemHeaderNames.some((name) => header.includes(name))
                  );
                  if (lineIndex < 0) lineIndex = 0;
                  if (itemIndex < 0) itemIndex = 1;
                  const result = [];
                  for (const row of body.querySelectorAll(':scope > tr')) {
                    const cells = row.querySelectorAll(':scope > td');
                    const lineNumber = clean(cells[lineIndex]?.textContent);
                    const customerItemNumber = clean(
                      cells[itemIndex]?.textContent
                    );
                    if (!lineNumber && !customerItemNumber) continue;
                    result.push({ lineNumber, customerItemNumber });
                  }
                  return result;
                }""",
                lines_table,
            )
        except Exception as exc:
            raise RpaBusinessError(
                "ORDER_DETAIL_LINES_UNAVAILABLE",
                "Customer purchase order detail lines could not be read",
            ) from exc
        if not isinstance(raw_lines, list) or not raw_lines:
            raise RpaBusinessError(
                "ORDER_DETAIL_LINES_UNAVAILABLE",
                "Customer purchase order detail lines are unavailable",
            )

        lines = []
        for index, raw_line in enumerate(raw_lines):
            if not isinstance(raw_line, Mapping):
                raise RpaBusinessError(
                    "ORDER_DETAIL_LINES_UNAVAILABLE",
                    "Customer purchase order detail line identity is invalid",
                    details={"index": index},
                )
            line_number = _clean(raw_line.get("lineNumber"))
            customer_item_number = _clean(raw_line.get("customerItemNumber"))
            if not line_number or not customer_item_number:
                raise RpaBusinessError(
                    "ORDER_DETAIL_LINES_UNAVAILABLE",
                    "Customer purchase order detail line identity is incomplete",
                    details={"index": index},
                )
            lines.append(
                {
                    "lineNumber": line_number,
                    "customerItemNumber": customer_item_number,
                }
            )
        return lines

    async def download_order(self):
        step_id = "file.download"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Downloading customer purchase order attachment",
            payload={"stepId": step_id, "stepType": step_id},
        )
        try:
            download_btn = self.page.locator(self.selector("download_order")).first
            await download_btn.wait_for(state="visible", timeout=8000)
            async with self.page.expect_download(timeout=15000) as info:
                await download_btn.click()
                confirm = self.page.locator(self.selector("download_confirm"))
                try:
                    if await confirm.count():
                        await confirm.first.click(timeout=2500)
                except Exception:
                    pass
            download = await info.value
            name = _clean(getattr(download, "suggested_filename", ""))
            if not name.lower().endswith(".xlsx"):
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_INVALID",
                    "Supplier portal returned an unexpected attachment type",
                )
            path = Path(await download.path())
            content = await asyncio.to_thread(path.read_bytes)
            attachment = await asyncio.to_thread(parse_order_xlsx, content)
            artifact = await self.ctx.artifacts.save_download(
                download, name, step_id=step_id
            )
            if (
                not isinstance(getattr(artifact, "size", None), int)
                or artifact.size <= 0
            ):
                raise RpaRetryableError(
                    "ORDER_ATTACHMENT_EMPTY",
                    "Supplier portal returned an empty order attachment",
                )
        except (RpaBusinessError, RpaRetryableError):
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_ATTACHMENT_DOWNLOAD_FAILED",
                "Customer purchase order attachment could not be downloaded",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Customer purchase order attachment parsed",
            payload={"stepId": step_id, "lineCount": len(attachment["lines"])},
        )
        return attachment

    async def wait_for_detail_stable(self):
        try:
            await self.page.locator(self.selector("download_dialog")).first.wait_for(
                state="hidden",
                timeout=10000,
            )
            await self.page.locator(self.selector("detail_page")).first.wait_for(
                state="visible",
                timeout=10000,
            )
            await self.page.locator(self.selector("download_order")).first.wait_for(
                state="visible",
                timeout=10000,
            )
            await self.page.locator(self.selector("lines_table")).first.wait_for(
                state="visible",
                timeout=10000,
            )
            await self.page.locator(self.selector("loading_mask")).first.wait_for(
                state="hidden",
                timeout=10000,
            )
            await self.page.evaluate(
                """
                async (detailSelector) => {
                  const detail = document.querySelector(detailSelector);
                  if (!detail) throw new Error('order detail is unavailable');
                  const visible = (node) => {
                    const rect = node.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                  };
                  const images = [...detail.querySelectorAll('img')].filter(visible);
                  const fontsReady = document.fonts?.ready ?? Promise.resolve();
                  const imagesReady = Promise.all(images.map((image) => {
                    if (image.complete) {
                      return image.naturalWidth > 0
                        ? Promise.resolve()
                        : Promise.reject(new Error('visible image failed to load'));
                    }
                    return new Promise((resolve, reject) => {
                      image.addEventListener('load', resolve, {once: true});
                      image.addEventListener(
                        'error',
                        () => reject(new Error('visible image failed to load')),
                        {once: true},
                      );
                    });
                  }));
                  const timeout = new Promise((_, reject) => {
                    setTimeout(
                      () => reject(new Error('page assets did not settle')),
                      10000,
                    );
                  });
                  await Promise.race([
                    Promise.all([fontsReady, imagesReady]),
                    timeout,
                  ]);
                }
                """,
                self.selector("detail_page"),
            )

            previous_layout = None
            for attempt in range(20):
                layout = await self.page.evaluate(
                    """
                    ({detailSelector, rowSelector}) => {
                      const detail = document.querySelector(detailSelector);
                      if (!detail) return null;
                      const measure = (node) => {
                        const rect = node.getBoundingClientRect();
                        return [
                          Math.round(rect.x),
                          Math.round(rect.y),
                          Math.round(rect.width),
                          Math.round(rect.height),
                        ];
                      };
                      return JSON.stringify({
                        detail: measure(detail),
                        scrollWidth: detail.scrollWidth,
                        scrollHeight: detail.scrollHeight,
                        rows: [...document.querySelectorAll(rowSelector)].map(measure),
                      });
                    }
                    """,
                    {
                        "detailSelector": self.selector("detail_page"),
                        "rowSelector": (
                            f"{self.selector('lines_table')} "
                            ".el-table__body-wrapper tbody tr"
                        ),
                    },
                )
                if layout is not None and layout == previous_layout:
                    break
                previous_layout = layout
                if attempt < 19:
                    await self.page.wait_for_timeout(150)
            else:
                raise RpaRetryableError(
                    "ORDER_DETAIL_STABILITY_TIMEOUT",
                    "Customer purchase order detail did not become stable",
                )
            await self.page.wait_for_timeout(300)
        except RpaRetryableError:
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DETAIL_STABILITY_TIMEOUT",
                "Customer purchase order detail did not become stable",
            ) from exc


async def run(ctx):
    client_id, client_secret = _erp_credentials(
        _ctx_text(ctx, "erpClientId"),
        _ctx_text(ctx, "erpClientSecret"),
    )
    erp_base = _require_erp_base(ctx)
    draft = await _prepare_erp_order(ctx)
    erp_payload = draft["erpPayload"]
    task_input = ctx.input if isinstance(ctx.input, Mapping) else {}
    po_no = _clean(task_input.get("po_no")).upper()
    line_count = len(erp_payload[0].get("lines", []))
    order_summary = _build_order_summary(po_no, draft)

    await _emit_erp_event_safely(
        ctx,
        "STEP_STARTED",
        message="Requesting ERP access token",
        payload={"stepId": "erp.oauth", "stepType": "erp.oauth"},
    )
    erp_step_id = "erp.oauth"
    try:
        async with ErpSalesOrderClient(
            token_url=_join_url(erp_base, ERP_TOKEN_PATH),
            import_url=_join_url(erp_base, ERP_ORDER_IMPORT_PATH),
            client_id=client_id,
            client_secret=client_secret,
            http_client=ctx.http,
        ) as erp_client:
            token_type, access_token = await erp_client.fetch_access_token()
            await _emit_erp_event_safely(
                ctx,
                "STEP_SUCCEEDED",
                message="ERP access token acquired",
                payload={"stepId": "erp.oauth"},
            )
            erp_step_id = "erp.import"
            await _emit_erp_event_safely(
                ctx,
                "STEP_STARTED",
                message="Importing ERP sales order",
                payload={
                    "stepId": "erp.import",
                    "stepType": "erp.import",
                    "poNo": po_no,
                    "lineCount": line_count,
                },
            )
            try:
                erp_result = await erp_client.import_sales_order(
                    erp_payload,
                    token_type,
                    access_token,
                )
                erp_order_number = _erp_order_number(erp_result)
                erp_header_id = _erp_header_id(erp_result)
            except asyncio.CancelledError:
                raise RpaHumanRequiredError(
                    "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                    "ERP sales order submission requires manual verification",
                ) from None
    except (
        RpaBusinessError,
        RpaFatalError,
        RpaHumanRequiredError,
        RpaRetryableError,
    ) as error:
        waiting_human = isinstance(error, RpaHumanRequiredError)
        if error.code == "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN":
            raise
        error_payload = {
            "stepId": erp_step_id,
            "errorCode": error.code,
            "poNo": po_no,
        }
        if error.code == "ERP_ORDER_IMPORT_ROW_FAILED":
            error_payload["rows"] = error.details.get("rows", [])
        await _emit_erp_event_safely(
            ctx,
            "STEP_WAITING_HUMAN" if waiting_human else "STEP_FAILED",
            level="WARNING" if waiting_human else "ERROR",
            message=error.safe_message,
            payload=error_payload,
        )
        raise

    try:
        await _emit_erp_event_safely(
            ctx,
            "ERP_ORDER_IMPORT_SUCCEEDED",
            message="ERP sales order import completed",
            payload={
                "stepId": "erp.import",
                **order_summary,
                "orderNumber": erp_order_number,
                "headerId": erp_header_id,
                "code": erp_result["code"],
                "success": erp_result["success"],
                "total": erp_result["total"],
                "rows": erp_result["rows"],
            },
        )
    except asyncio.CancelledError:
        raise RpaHumanRequiredError(
            "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
            "ERP sales order submission requires manual verification",
        ) from None
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "poNo": order_summary["poNo"],
        "orderNumber": erp_order_number,
        "headerId": erp_header_id,
        "supplierCode": order_summary["supplierCode"],
        "supplierName": order_summary["supplierName"],
        "lineCount": order_summary["lineCount"],
        "lines": order_summary["lines"],
    }


async def _prepare_erp_order(ctx):
    if not ctx.portal_url:
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")
    task_input = ctx.input if isinstance(ctx.input, Mapping) else {}
    po_no = _clean(task_input.get("po_no")).upper()
    if not PO_NUMBER_PATTERN.fullmatch(po_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Customer purchase order number is missing or invalid",
        )
    await ctx.log.info("Starting supplier portal ERP draft Flow", {"poNo": po_no})
    adapter = SupplierPortalAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)
    portal_lines = await adapter.collect_order_line_identities()
    attachment = await adapter.download_order()
    normalized_attachment, reconciliation = reconcile_attachment_with_portal(
        po_no,
        portal_lines,
        attachment,
    )
    await ctx.events.emit(
        "ORDER_ATTACHMENT_RECONCILED",
        message="Order attachment lines matched the portal detail",
        payload={
            "poNo": po_no,
            **reconciliation,
        },
    )
    erp_payload, resolved_lines = build_erp_draft(
        po_no,
        normalized_attachment,
        customer_name=_customer_name_from_ctx(ctx),
        org_name=_org_name_from_ctx(ctx),
        customer_sub_code=_customer_sub_code_from_ctx(ctx),
        org_code=_org_code_from_ctx(ctx),
    )
    await adapter.wait_for_detail_stable()
    await ctx.artifacts.screenshot(
        "supplier-portal-erp-draft-prepared",
        step_id="erp.prepare",
    )
    await ctx.events.emit(
        "ERP_ORDER_DRAFT_PREPARED",
        message="ERP order draft was prepared without transmission",
        payload={
            "poNo": po_no,
            "lineCount": len(resolved_lines),
            "transmitted": False,
        },
    )
    return {
        "draftOnly": True,
        "transmitted": False,
        "orderDetail": {
            "sheetName": normalized_attachment["sheetName"],
            "supplierCode": normalized_attachment["supplierCode"],
            "supplierName": normalized_attachment["supplierName"],
            "lines": resolved_lines,
        },
        "erpPayload": erp_payload,
    }
