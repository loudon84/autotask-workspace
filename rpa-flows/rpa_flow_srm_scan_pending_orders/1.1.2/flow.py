import io
import re
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaRetryableError,
    login_official_srm,
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
PENDING_REPLY_STATUS = "待签章"
OUTPUT_SCHEMA_VERSION = "SRM_PENDING_ORDERS_OUTPUT_V1"
DEFAULT_DRILL_PO = "POJS2607170008"
MAX_XLSX_BYTES = 10 * 1024 * 1024
MAX_XLSX_FILES = 100
MAX_XLSX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
EXPORT_TIMEOUT_MS = 30000

HEADER_ALIASES = {
    "poNo": ("订单编号", "采购单号"),
    "orderDate": ("日期", "订单日期", "单据日期"),
    "orderType": ("订单类型",),
    "totalAmount": ("总金额(元)", "总金额（元）", "总金额"),
    "replyStatus": ("回复状态",),
    "deliveryStatus": ("交货状态", "发货状态"),
    "supplierName": ("供应商单位", "供应商名称", "主体"),
}


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_captcha_code(image_src):
    if not isinstance(image_src, str) or not image_src.strip():
        return None
    clean_src = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean_src.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


def resolve_drill_po(raw_input):
    """演练单号：默认 POJS2607170008；Binding/任务 input 可覆盖；空字符串关闭。"""
    if not isinstance(raw_input, Mapping):
        return DEFAULT_DRILL_PO
    if "assumedPendingPo" not in raw_input and "assumed_pending_po" not in raw_input:
        return DEFAULT_DRILL_PO
    configured = raw_input.get("assumedPendingPo")
    if configured is None:
        configured = raw_input.get("assumed_pending_po")
    text = _clean(configured).upper()
    return text or None


def _pick_header(headers, names):
    for name in names:
        if name in headers:
            return name
        for header in headers:
            if name in header:
                return header
    return None


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
            "ORDER_LIST_EXPORT_INVALID",
            "Exported workbook contains an unsafe worksheet path",
        )
    return path.as_posix()


def read_xlsx_table(content):
    """把列表导出的 xlsx 读成表头 dict 行；空文件返回 []。"""
    if not isinstance(content, bytes) or not content.startswith(b"PK\x03\x04"):
        raise RpaBusinessError(
            "ORDER_LIST_EXPORT_INVALID",
            "Exported order list is not a valid XLSX file",
        )
    if len(content) > MAX_XLSX_BYTES:
        raise RpaBusinessError(
            "ORDER_LIST_EXPORT_TOO_LARGE",
            "Exported order list exceeds the Flow size limit",
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
                    "ORDER_LIST_EXPORT_INVALID",
                    "Exported workbook contains too many files",
                )
            if sum(item.file_size for item in infos) > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise RpaBusinessError(
                    "ORDER_LIST_EXPORT_INVALID",
                    "Exported workbook expands beyond the Flow size limit",
                )
            names = set(archive.namelist())
            required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            if not required.issubset(names):
                raise RpaBusinessError(
                    "ORDER_LIST_EXPORT_INVALID",
                    "Exported workbook metadata is missing",
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
                return []
            sheet = list(sheets)[0]
            target = _xlsx_target(targets[sheet.attrib[f"{{{office_ns}}}id"]])
            if target not in names:
                raise RpaBusinessError(
                    "ORDER_LIST_EXPORT_INVALID",
                    "Exported worksheet is missing",
                )
            worksheet = ET.fromstring(archive.read(target))
            table_rows = []
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
                    table_rows.append(values)
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
            "ORDER_LIST_EXPORT_INVALID",
            "Exported order list could not be parsed",
        ) from exc
    if not table_rows:
        return []
    headers = [_clean(value) for value in table_rows[0]]
    records = []
    for values in table_rows[1:]:
        record = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            record[header] = values[index] if index < len(values) else ""
        if any(_clean(value) for value in record.values()):
            records.append(record)
    return records


def map_export_row(raw):
    if not isinstance(raw, Mapping):
        return None
    mapped = {}
    for field, names in HEADER_ALIASES.items():
        header = _pick_header(list(raw.keys()), names)
        mapped[field] = _clean(raw.get(header) if header else raw.get(field))
    po_no = mapped["poNo"].upper()
    if not po_no:
        return None
    mapped["poNo"] = po_no
    return mapped


def orders_from_export_rows(raw_rows, *, treat_as_pending=False):
    """Excel 行转扫单 output.orders。待签章搜索只留待签章；演练回退把导出行当成待签章。"""
    if not isinstance(raw_rows, list):
        raise RpaBusinessError(
            "ORDER_LIST_UNAVAILABLE",
            "Supplier portal order list export could not be read",
        )
    orders = []
    seen = set()
    for raw in raw_rows:
        mapped = map_export_row(raw)
        if mapped is None:
            continue
        po_no = mapped["poNo"]
        if po_no in seen:
            continue
        if not treat_as_pending and mapped.get("replyStatus") != PENDING_REPLY_STATUS:
            continue
        seen.add(po_no)
        orders.append(
            {
                "poNo": po_no,
                "orderDate": mapped.get("orderDate") or "",
                "orderType": mapped.get("orderType") or "",
                "totalAmount": mapped.get("totalAmount") or "",
                "replyStatus": PENDING_REPLY_STATUS,
                "deliveryStatus": mapped.get("deliveryStatus") or "",
                "supplierName": mapped.get("supplierName") or "",
            }
        )
    return orders


def filter_pending_orders(raw_rows):
    """兼容旧测试：从已映射/原始行里提取待签章。"""
    if not isinstance(raw_rows, list):
        raise RpaBusinessError(
            "ORDER_LIST_UNAVAILABLE",
            "Supplier portal order list could not be read",
        )
    normalized = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        if "poNo" in raw or "replyStatus" in raw:
            normalized.append(raw)
        else:
            mapped = map_export_row(raw)
            if mapped is not None:
                normalized.append(mapped)
    return orders_from_export_rows(normalized, treat_as_pending=False)


async def _safe_emit(ctx, event_type, *, level="INFO", message, payload=None):
    try:
        await ctx.events.emit(event_type, level=level, message=message, payload=payload)
    except Exception:
        return


async def _safe_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return


class SupplierPortalScanAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.page
        self.selectors = ctx.selectors

    def selector(self, name, **values):
        value = self.selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError(
                "FLOW_SELECTOR_MISSING",
                f"Required supplier portal selector is missing: {name}",
            )
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    async def login(self):
        await login_official_srm(self.ctx, selector=self.selector)

    async def open_order_list(self):
        step_id = "srm.open_order_list"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Opening supplier portal order list",
            payload={"stepId": step_id, "stepType": step_id},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        try:
            await self.page.goto(f"{portal_root}/#/order/list", wait_until="domcontentloaded")
            await self.page.locator(self.selector("order_page")).wait_for(
                state="visible", timeout=10000
            )
            await self._wait_loading_done()
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_LIST_UNAVAILABLE",
                "Supplier portal order list could not be opened",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Supplier portal order list opened",
            payload={"stepId": step_id},
        )

    async def _wait_loading_done(self):
        try:
            await self.page.locator(self.selector("loading_mask")).wait_for(
                state="hidden", timeout=15000
            )
        except Exception:
            pass

    async def select_form_option(self, label, option):
        item = self.page.locator(".el-form-item").filter(
            has=self.page.locator(".el-form-item__label", has_text=label)
        ).first
        if await item.count() == 0:
            raise RpaRetryableError(
                "ORDER_LIST_FILTER_UNAVAILABLE",
                f"Supplier portal filter is missing: {label}",
            )
        trigger = item.locator(".el-select input, .el-input__inner, input").first
        await trigger.click(timeout=4000)
        await self.page.wait_for_timeout(400)
        option_loc = self.page.locator(
            ".el-select-dropdown:visible li, .el-select-dropdown:visible .el-option"
        ).filter(has_text=option).first
        try:
            await option_loc.click(timeout=4000)
        except Exception as exc:
            await self.page.keyboard.press("Escape")
            raise RpaRetryableError(
                "ORDER_LIST_FILTER_UNAVAILABLE",
                f"Supplier portal filter option is missing: {label}={option}",
            ) from exc
        await self.page.wait_for_timeout(200)

    async def fill_form_input(self, label, value):
        item = self.page.locator(".el-form-item").filter(
            has=self.page.locator(".el-form-item__label", has_text=label)
        ).first
        if await item.count() == 0:
            raise RpaRetryableError(
                "ORDER_LIST_FILTER_UNAVAILABLE",
                f"Supplier portal filter is missing: {label}",
            )
        box = item.locator("input:visible").first
        await box.fill(value, timeout=4000)

    async def click_search(self):
        await self.page.locator(self.selector("search_button")).click(timeout=4000)
        await self._wait_loading_done()
        await self.page.wait_for_timeout(500)

    async def click_reset(self):
        reset = self.page.locator(self.selector("reset_button"))
        if await reset.count() == 0:
            return False
        await reset.click(timeout=4000)
        await self._wait_loading_done()
        await self.page.wait_for_timeout(300)
        return True

    async def search_pending_signature(self):
        await self.select_form_option("回复状态", PENDING_REPLY_STATUS)
        await self.click_search()

    async def search_by_po_no(self, po_no):
        await self.click_reset()
        await self.fill_form_input("订单编号", po_no)
        await self.click_search()

    async def result_is_empty(self):
        empty = self.page.locator(self.selector("empty_text"))
        try:
            if await empty.count() and await empty.first.is_visible():
                return True
        except Exception:
            pass
        rows = self.page.locator(".el-table__body-wrapper tbody tr:visible")
        try:
            return await rows.count() == 0
        except Exception:
            return False

    async def export_xlsx(self, artifact_name):
        step_id = "file.download"
        export_button = self.page.locator(self.selector("export_button")).first
        try:
            await export_button.wait_for(state="visible", timeout=5000)
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_LIST_EXPORT_UNAVAILABLE",
                "Supplier portal export button is unavailable",
            ) from exc
        disabled = False
        try:
            disabled = await export_button.is_disabled()
        except Exception:
            disabled = False
        if disabled:
            return None
        try:
            async with self.page.expect_download(timeout=EXPORT_TIMEOUT_MS) as info:
                await export_button.click(timeout=4000)
                confirm = self.page.locator(self.selector("export_confirm"))
                try:
                    if await confirm.count():
                        await confirm.first.click(timeout=2500)
                except Exception:
                    pass
            download = await info.value
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_LIST_EXPORT_FAILED",
                "Supplier portal order list export did not start",
            ) from exc
        name = _clean(getattr(download, "suggested_filename", "")) or artifact_name
        if not name.lower().endswith(".xlsx"):
            raise RpaBusinessError(
                "ORDER_LIST_EXPORT_INVALID",
                "Supplier portal export is not an XLSX file",
            )
        path = Path(await download.path())
        content = path.read_bytes()
        await self.ctx.artifacts.save_download(download, name, step_id=step_id)
        return content


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError(
            "PORTAL_URL_MISSING",
            "Supplier portal URL is unavailable",
        )
    await ctx.log.info("Starting supplier portal pending-order scan Flow")
    raw_input = ctx.input if isinstance(getattr(ctx, "input", None), Mapping) else {}
    drill_po = resolve_drill_po(raw_input)

    adapter = SupplierPortalScanAdapter(ctx)
    await adapter.login()
    await adapter.open_order_list()

    step_id = "srm.scan_pending_orders"
    await ctx.events.emit(
        "STEP_STARTED",
        message="Searching pending-signature orders and exporting Excel",
        payload={"stepId": step_id, "stepType": step_id},
    )
    await adapter.search_pending_signature()
    await _safe_screenshot(ctx, "supplier-portal-pending-orders", step_id)

    pending_empty = await adapter.result_is_empty()
    pending_content = None
    if not pending_empty:
        pending_content = await adapter.export_xlsx("pending-orders.xlsx")
    pending_rows = read_xlsx_table(pending_content) if pending_content else []
    orders = orders_from_export_rows(pending_rows, treat_as_pending=False)
    drill = None
    source_filter = "replyStatus=待签章"

    if not orders and drill_po:
        await adapter.search_by_po_no(drill_po)
        await _safe_screenshot(ctx, "supplier-portal-drill-po", step_id)
        if await adapter.result_is_empty():
            raise RpaBusinessError(
                "ORDER_LIST_UNAVAILABLE",
                f"Drill purchase order was not found: {drill_po}",
            )
        drill_content = await adapter.export_xlsx("drill-order.xlsx")
        if not drill_content:
            raise RpaRetryableError(
                "ORDER_LIST_EXPORT_UNAVAILABLE",
                "Supplier portal export is disabled for the drill purchase order",
            )
        drill_rows = read_xlsx_table(drill_content)
        orders = orders_from_export_rows(drill_rows, treat_as_pending=True)
        source_filter = f"订单编号={drill_po}"
        drill = {
            "assumedPending": True,
            "poNo": drill_po,
            "note": "正式站无待签章，演练按订单编号搜索后导出，当成待签章扫入",
        }

    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Pending-signature orders collected from Excel export",
        payload={
            "stepId": step_id,
            "totalRows": len(orders),
            "pendingCount": len(orders),
            "sourceFilter": source_filter,
            "assumedPending": bool(drill),
        },
    )
    await ctx.log.info(
        "Supplier portal pending-order scan completed",
        {
            "totalRows": len(orders),
            "pendingCount": len(orders),
            "sourceFilter": source_filter,
            "assumedPending": bool(drill),
        },
    )
    result = {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "portalUrl": ctx.portal_url,
        "totalRows": len(orders),
        "orders": orders,
        "source": "xlsx",
        "sourceFilter": source_filter,
    }
    if drill is not None:
        result["drill"] = drill
    return result
