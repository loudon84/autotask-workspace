import asyncio
import io
import re
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from nodeskclaw_rpa_engine.runtime import (
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
DEFAULT_CUSTOMER_NAME = "天地偉業技術有限公司"
DEFAULT_ORDER_TYPE = "常规订单"
DEFAULT_TAX_RATE = Decimal("0.13")
CHINA_TIMEZONE = timezone(timedelta(hours=8))

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
    office_ns = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
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
                        "".join(node.text or "" for node in item.iter(f"{{{main_ns}}}t"))
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
    except (KeyError, IndexError, OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
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
            {target: raw.get(source, "") for source, target in ATTACHMENT_FIELD_MAP.items()}
        )
    if not records:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_DATA_INCOMPLETE",
            "Order attachment does not contain order lines",
        )
    suppliers = {
        (_clean(item["supplierCode"]), _clean(item["supplierName"]))
        for item in records
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


def _attachment_comments(lines):
    comments = []
    for line in lines:
        value = _clean(line.get("remarks"))
        if value and value not in comments:
            comments.append(value)
    return "；".join(comments)


def build_erp_draft(po_no, attachment, ordered_date=None):
    normalized_po = _clean(po_no).upper()
    attachment_orders = {_clean(line["poNo"]).upper() for line in attachment["lines"]}
    if attachment_orders != {normalized_po}:
        raise RpaBusinessError(
            "ORDER_ATTACHMENT_PO_MISMATCH",
            "Order attachment does not match the requested purchase order",
        )
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
            "taxRate": _json_number(DEFAULT_TAX_RATE),
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
        "customerName": DEFAULT_CUSTOMER_NAME,
        "salesrep": "",
        "invoiceToLocation": "",
        "orderType": DEFAULT_ORDER_TYPE,
        "orderedDate": _erp_text(resolved_ordered_date, "orderedDate"),
        "currencyCode": "",
        "orgCode": "",
        "orgName": _erp_text(attachment.get("supplierName"), "orgName"),
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
        "orderType",
        "orderedDate",
        "orgName",
        "isAttachment",
    )
    required_line = (
        "custPoLine",
        "custPoNumber",
        "custItemNum",
        "orderQuantity",
        "unitSellingPrice",
        "taxRate",
        "requestDate",
    )
    if any(header.get(name) in (None, "") for name in required_header):
        raise RpaBusinessError(
            "ERP_REQUIRED_FIELD_MISSING",
            "ERP order header is missing a required field",
        )
    if any(any(line.get(name) in (None, "") for name in required_line) for line in erp_lines):
        raise RpaBusinessError(
            "ERP_REQUIRED_FIELD_MISSING",
            "ERP order line is missing a required field",
        )
    return [header], resolved_lines


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
        step_id = "srm.login"
        username = _clean(self.ctx.credentials.get("username"))
        password = str(self.ctx.credentials.get("password", ""))
        if not username or not password:
            raise RpaFatalError(
                "SRM_CREDENTIALS_MISSING",
                "Supplier portal credentials are unavailable",
            )
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Logging in to supplier portal",
            payload={"stepId": step_id, "stepType": step_id},
        )
        await self.page.goto(self.ctx.portal_url, wait_until="domcontentloaded")
        captcha = self.page.locator(self.selector("captcha_image"))
        await captcha.wait_for(state="visible", timeout=10000)
        code = resolve_captcha_code(await captcha.get_attribute("src"))
        if code is None:
            await self._redact_login_fields()
            await self.ctx.artifacts.screenshot("supplier-portal-captcha-unknown", step_id=step_id)
            raise RpaHumanRequiredError(
                "HUMAN_VERIFICATION_REQUIRED",
                "Supplier portal CAPTCHA requires human verification",
            )
        try:
            await self.page.fill(self.selector("username"), username)
            await self.page.fill(self.selector("password"), password)
            await self.page.fill(self.selector("captcha"), code)
            agreement = self.page.locator(self.selector("agreement"))
            if not await agreement.is_checked():
                await agreement.check()
            await self.page.click(self.selector("login_button"))
            await self._wait_for_login_result()
        except (RpaBusinessError, RpaRetryableError):
            raise
        except Exception as exc:
            await self._redact_login_fields()
            raise RpaRetryableError(
                "SRM_LOGIN_FAILED",
                "Supplier portal login failed",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Supplier portal login completed",
            payload={"stepId": step_id},
        )

    async def _wait_for_login_result(self):
        success = self.page.locator(self.selector("login_success"))
        error = self.page.locator(self.selector("login_error"))
        for _ in range(50):
            if await success.is_visible():
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

    async def open_order_detail(self, po_no):
        step_id = "srm.search_po"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Opening customer purchase order detail",
            payload={"stepId": step_id, "stepType": step_id},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        await self.page.goto(
            f"{portal_root}/#/supplier/orders",
            wait_until="domcontentloaded",
        )
        await self.page.locator(self.selector("order_page")).wait_for(
            state="visible",
            timeout=10000,
        )
        await self.page.fill(self.selector("po_number"), po_no)
        await self.page.click(self.selector("search_button"))
        row = self.page.locator(self.selector("order_row", po_no))
        try:
            await row.wait_for(state="visible", timeout=10000)
        except Exception as exc:
            raise RpaBusinessError(
                "BUSINESS_NOT_FOUND",
                "Customer purchase order was not found",
            ) from exc
        await self.page.click(self.selector("order_detail", po_no))
        try:
            await self.page.locator(self.selector("detail_po_number", po_no)).wait_for(
                state="visible", timeout=15000
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

    async def download_order(self):
        step_id = "file.download"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Downloading customer purchase order attachment",
            payload={"stepId": step_id, "stepType": step_id},
        )
        await self.page.click(self.selector("download_order"))
        confirm = self.page.locator(self.selector("download_confirm"))
        try:
            await confirm.wait_for(state="visible", timeout=5000)
            async with self.page.expect_download(timeout=15000) as info:
                await confirm.click()
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
            artifact = await self.ctx.artifacts.save_download(download, name, step_id=step_id)
            if not isinstance(getattr(artifact, "size", None), int) or artifact.size <= 0:
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


async def run(ctx):
    if not ctx.portal_url:
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")
    po_no = _clean(ctx.input.get("po_no")).upper()
    if not PO_NUMBER_PATTERN.fullmatch(po_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Customer purchase order number is missing or invalid",
        )
    await ctx.log.info("Starting supplier portal ERP draft Flow", {"poNo": po_no})
    adapter = SupplierPortalAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)
    attachment = await adapter.download_order()
    erp_payload, resolved_lines = build_erp_draft(po_no, attachment)
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
            "sheetName": attachment["sheetName"],
            "supplierCode": attachment["supplierCode"],
            "supplierName": attachment["supplierName"],
            "lines": resolved_lines,
        },
        "erpPayload": erp_payload,
    }
