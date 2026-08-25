"""SRM 收货列表查询（对账单生成前，正式门户）。

输入：dateStart / dateEnd（YYYY-MM-DD）
操作：入库确认时间范围面板选日（00:00:00–23:59:59）→ 对账状态=未提交 → 查询 → 导出 Excel
输出：{ schemaVersion, portalUrl, totalRows, rows[] }
"""

import io
import re
import zipfile
from collections.abc import Mapping
from datetime import date, timedelta
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
OUTPUT_SCHEMA_VERSION = "SRM_STMT_RECEIPTS_OUTPUT_V1"
UNSUBMITTED_STATUS = "未提交"
RECONCILE_STATUS_LABEL = "对账状态"
START_TIME = "00:00:00"
END_TIME = "23:59:59"
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MAX_XLSX_BYTES = 10 * 1024 * 1024
MAX_XLSX_FILES = 100
MAX_XLSX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
EXPORT_TIMEOUT_MS = 30000
EXCEL_EPOCH = date(1899, 12, 30)

READ_PICKER_MONTHS_JS = r"""() => {
  const panel = [...document.querySelectorAll('.el-date-range-picker')]
    .find((el) => el.offsetParent !== null);
  if (!panel) return { months: [] };
  const parse = (el) => {
    const text = ((el.querySelector('.el-date-range-picker__header') || el).innerText || '');
    const match = text.match(/(\d{4})\s*年\s*(\d{1,2})\s*月/);
    return match ? { year: Number(match[1]), month: Number(match[2]) } : null;
  };
  return {
    months: [...panel.querySelectorAll('.el-date-range-picker__content')]
      .map(parse)
      .filter(Boolean),
  };
}"""

CLICK_PICKER_DAY_JS = r"""({ year, month, day }) => {
  const panel = [...document.querySelectorAll('.el-date-range-picker')]
    .find((el) => el.offsetParent !== null);
  if (!panel) return 'no-panel';
  const parse = (el) => {
    const text = ((el.querySelector('.el-date-range-picker__header') || el).innerText || '');
    const match = text.match(/(\d{4})\s*年\s*(\d{1,2})\s*月/);
    return match ? [Number(match[1]), Number(match[2])] : [0, 0];
  };
  const content = [...panel.querySelectorAll('.el-date-range-picker__content')]
    .find((el) => {
      const [y, m] = parse(el);
      return y === year && m === month;
    });
  if (!content) return 'month-missing';
  const cell = [...content.querySelectorAll('td')].find((td) => {
    const cls = td.className || '';
    if (cls.includes('prev-month') || cls.includes('next-month') || cls.includes('disabled')) {
      return false;
    }
    return String(td.innerText || '').trim() === String(day);
  });
  if (!cell) return 'day-missing';
  cell.click();
  return 'ok';
}"""


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def resolve_captcha_code(src):
    text = _clean(src).lower()
    for key, code in CAPTCHA_CODES.items():
        if key in text:
            return code
    return None


def parse_ymd(value):
    match = DATE_RE.fullmatch(_clean(value))
    if not match:
        raise RpaFatalError(
            "STMT_DATE_RANGE_INVALID",
            "dateStart/dateEnd must be YYYY-MM-DD",
        )
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise RpaFatalError(
            "STMT_DATE_RANGE_INVALID",
            "dateStart/dateEnd must be a real calendar date",
        ) from exc


def month_nav_action(left_year, left_month, target_year, target_month, right_year=None, right_month=None):
    if (left_year, left_month) == (target_year, target_month):
        return "visible-left"
    if right_year is not None and (right_year, right_month) == (target_year, target_month):
        return "visible-right"
    left = left_year * 12 + left_month
    target = target_year * 12 + target_month
    if target < left:
        return "year-prev" if target_year < left_year else "month-prev"
    if right_year is not None:
        right = right_year * 12 + right_month
        if target > right:
            return "year-next" if target_year > right_year else "month-next"
        return "visible-right"
    return "year-next" if target_year > left_year else "month-next"


def excel_serial_to_date(value):
    text = _clean(value)
    if not re.fullmatch(r"\d+(\.\d+)?", text):
        return text
    serial = float(text)
    if serial < 20000 or serial > 80000:
        return text
    return (EXCEL_EPOCH + timedelta(days=int(serial))).isoformat()


def _as_date_text(value):
    text = excel_serial_to_date(value)
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else text


def normalize_receipt_row(raw):
    if not isinstance(raw, Mapping):
        return None
    receipt_no = _clean(
        raw.get("收货单号") or raw.get("receiptNo") or raw.get("receipt_no")
    )
    line_no = _clean(
        raw.get("收货单行号") or raw.get("lineNo") or raw.get("line_no") or raw.get("行号")
    )
    if not receipt_no or not line_no:
        return None
    amount = _clean(
        raw.get("可立账价税合计（元）")
        or raw.get("可立账价税合计")
        or raw.get("价税合计")
        or raw.get("taxIncludedAmount")
    ).replace(",", "")
    return {
        "receiptNo": receipt_no,
        "lineNo": line_no,
        "orderNo": _clean(raw.get("订单编号") or raw.get("orderNo")),
        "materialNumber": _clean(raw.get("料号") or raw.get("materialNumber")),
        "itemName": _clean(raw.get("料品名称") or raw.get("itemName")),
        "itemSpec": _clean(raw.get("料品规格") or raw.get("itemSpec")),
        "receivedQty": _clean(raw.get("实收数量") or raw.get("receivedQty")),
        "unitPrice": _clean(raw.get("单价（元）") or raw.get("单价(元)") or raw.get("unitPrice")),
        "untaxedUnitPrice": _clean(
            raw.get("未税单价（元）") or raw.get("未税单价") or raw.get("untaxedUnitPrice")
        ),
        "taxRate": _clean(raw.get("税率") or raw.get("taxRate")),
        "untaxedAmount": _clean(
            raw.get("可立账未税金额（元）") or raw.get("可立账未税金额") or raw.get("untaxedAmount")
        ).replace(",", ""),
        "taxAmount": _clean(
            raw.get("可立账税额（元）") or raw.get("可立账税额") or raw.get("taxAmount")
        ).replace(",", ""),
        "taxIncludedAmount": amount,
        "reconcileStatus": _clean(raw.get("对账状态") or raw.get("reconcileStatus")),
        "inboundConfirmDate": _as_date_text(
            raw.get("入库确认日期")
            or raw.get("入库确认时间")
            or raw.get("inboundConfirmDate")
        ),
        "docDate": _as_date_text(raw.get("单据日期") or raw.get("docDate")),
        "actualArrivalDate": _as_date_text(
            raw.get("实际到货日期") or raw.get("actualArrivalDate")
        ),
        "docType": _clean(raw.get("单据类型") or raw.get("docType")),
        "billQty": _clean(raw.get("立账数量") or raw.get("billQty")),
        "supplierCode": _clean(raw.get("供应商编号") or raw.get("supplierCode")),
        "supplierName": _clean(raw.get("供应商名称") or raw.get("supplierName")),
    }


def normalize_receipt_rows(raw_rows):
    if not isinstance(raw_rows, list):
        raise RpaBusinessError(
            "SRM_STMT_RECEIPTS_INVALID",
            "Receipt list payload is invalid",
        )
    rows = []
    seen = set()
    for raw in raw_rows:
        row = normalize_receipt_row(raw)
        if row is None:
            continue
        if row.get("reconcileStatus") and row["reconcileStatus"] not in {
            UNSUBMITTED_STATUS,
            "未对账",
        }:
            continue
        key = (row["receiptNo"], row["lineNo"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


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
            "SRM_STMT_RECEIPTS_EXPORT_INVALID",
            "Exported workbook contains an unsafe worksheet path",
        )
    return path.as_posix()


def read_xlsx_table(content):
    """把列表导出的 xlsx 读成表头 dict 行；空文件返回 []。"""
    if not isinstance(content, bytes) or not content.startswith(b"PK\x03\x04"):
        raise RpaBusinessError(
            "SRM_STMT_RECEIPTS_EXPORT_INVALID",
            "Exported receipt list is not a valid XLSX file",
        )
    if len(content) > MAX_XLSX_BYTES:
        raise RpaBusinessError(
            "SRM_STMT_RECEIPTS_EXPORT_TOO_LARGE",
            "Exported receipt list exceeds the Flow size limit",
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
                    "SRM_STMT_RECEIPTS_EXPORT_INVALID",
                    "Exported workbook contains too many files",
                )
            if sum(item.file_size for item in infos) > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise RpaBusinessError(
                    "SRM_STMT_RECEIPTS_EXPORT_INVALID",
                    "Exported workbook expands beyond the Flow size limit",
                )
            names = set(archive.namelist())
            required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            if not required.issubset(names):
                raise RpaBusinessError(
                    "SRM_STMT_RECEIPTS_EXPORT_INVALID",
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
                    "SRM_STMT_RECEIPTS_EXPORT_INVALID",
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
            "SRM_STMT_RECEIPTS_EXPORT_INVALID",
            "Exported receipt list could not be parsed",
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


async def _safe_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return


async def _safe_emit(ctx, event_type, message="", payload=None):
    try:
        await ctx.events.emit(event_type, message=message, payload=payload or {})
    except Exception:
        return


class ReceiptListAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.page
        self.selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}

    def selector(self, name, **values):
        value = self.selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError(
                "FLOW_SELECTOR_MISSING",
                f"Required selector is missing: {name}",
            )
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    async def login(self):
        await login_official_srm(self.ctx, selector=self.selector)

    async def _wait_loading_done(self):
        try:
            await self.page.locator(self.selector("loading_mask")).wait_for(
                state="hidden", timeout=15000
            )
        except Exception:
            pass

    async def open_receipt_list(self, date_start: str, date_end: str):
        step_id = "srm.open_receipt_list"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Opening receipt list",
            payload={"stepId": step_id, "stepType": step_id},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        await self.page.goto(
            f"{portal_root}/#/order/receivingList", wait_until="domcontentloaded"
        )
        page = self.page.locator(self.selector("receipt_page"))
        try:
            await page.wait_for(state="visible", timeout=15000)
        except Exception as exc:
            await _safe_screenshot(self.ctx, "stmt-receipt-page-missing", step_id)
            raise RpaBusinessError(
                "SRM_STMT_RECEIPT_PAGE_MISSING",
                "Receipt list page is unavailable",
            ) from exc
        await self.pick_inbound_confirm_range(date_start, date_end)
        await self.select_form_option(RECONCILE_STATUS_LABEL, UNSUBMITTED_STATUS)
        await self.page.locator(self.selector("search_button")).click(timeout=4000)
        await self._wait_loading_done()
        await self.page.wait_for_timeout(500)
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Receipt list opened",
            payload={"stepId": step_id},
        )

    async def pick_inbound_confirm_range(self, date_start: str, date_end: str):
        start = parse_ymd(date_start)
        end = parse_ymd(date_end)
        if start > end:
            raise RpaFatalError(
                "STMT_DATE_RANGE_INVALID",
                "dateStart must be on or before dateEnd",
            )
        editor = self.page.locator(self.selector("date_range")).first
        try:
            await editor.wait_for(state="visible", timeout=8000)
            await editor.click(timeout=4000)
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Inbound confirm date range is unavailable",
            ) from exc
        panel = self.page.locator(self.selector("date_picker")).first
        try:
            await panel.wait_for(state="visible", timeout=5000)
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Inbound confirm date picker did not open",
            ) from exc
        await self._pick_calendar_day(start)
        await self._pick_calendar_day(end)
        await self._ensure_range_times(panel)
        confirm = self.page.locator(self.selector("date_picker_confirm")).first
        try:
            await confirm.click(timeout=4000)
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Inbound confirm date picker confirm is unavailable",
            ) from exc
        try:
            await panel.wait_for(state="hidden", timeout=4000)
        except Exception:
            await self.page.keyboard.press("Escape")

    async def _read_picker_months(self):
        payload = await self.page.evaluate(READ_PICKER_MONTHS_JS)
        months = payload.get("months") if isinstance(payload, Mapping) else []
        parsed = []
        for item in months if isinstance(months, list) else []:
            if not isinstance(item, Mapping):
                continue
            year = item.get("year")
            month = item.get("month")
            if isinstance(year, int) and isinstance(month, int):
                parsed.append((year, month))
        return parsed

    async def _ensure_month_visible(self, target: date):
        for _ in range(36):
            months = await self._read_picker_months()
            if not months:
                raise RpaRetryableError(
                    "SRM_STMT_DATE_RANGE_MISSING",
                    "Inbound confirm date picker months are unavailable",
                )
            left_year, left_month = months[0]
            right = months[1] if len(months) > 1 else (None, None)
            action = month_nav_action(
                left_year,
                left_month,
                target.year,
                target.month,
                right[0],
                right[1],
            )
            if action.startswith("visible"):
                return
            selector_name = {
                "year-prev": "date_picker_prev_year",
                "month-prev": "date_picker_prev_month",
                "month-next": "date_picker_next_month",
                "year-next": "date_picker_next_year",
            }[action]
            await self.page.locator(self.selector(selector_name)).first.click(timeout=2000)
            await self.page.wait_for_timeout(150)
        raise RpaRetryableError(
            "SRM_STMT_DATE_RANGE_MISSING",
            "Inbound confirm date picker could not reach the requested month",
        )

    async def _pick_calendar_day(self, target: date):
        await self._ensure_month_visible(target)
        result = await self.page.evaluate(
            CLICK_PICKER_DAY_JS,
            {"year": target.year, "month": target.month, "day": target.day},
        )
        if result != "ok":
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                f"Inbound confirm calendar day is unavailable: {target.isoformat()}",
            )
        await self.page.wait_for_timeout(150)

    async def _ensure_range_times(self, panel):
        editors = panel.locator(
            ".el-date-range-picker__time-header input, .el-date-range-picker__editor"
        )
        count = await editors.count()
        if count < 4:
            return
        await self._fill_if_needed(editors.nth(1), START_TIME)
        await self._fill_if_needed(editors.nth(3), END_TIME)

    async def _fill_if_needed(self, locator, value):
        current = ""
        try:
            current = _clean(await locator.input_value())
        except Exception:
            current = ""
        if current == value:
            return
        try:
            await locator.click(timeout=2000)
            await locator.fill(value, timeout=2000)
        except Exception:
            await locator.evaluate(
                """(el, v) => {
                  el.removeAttribute('readonly');
                  el.value = v;
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                value,
            )

    async def select_form_option(self, label, option):
        item = self.page.locator(".el-form-item").filter(
            has=self.page.locator(".el-form-item__label", has_text=label)
        ).first
        if await item.count() == 0:
            raise RpaRetryableError(
                "SRM_STMT_FILTER_UNAVAILABLE",
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
                "SRM_STMT_FILTER_UNAVAILABLE",
                f"Supplier portal filter option is missing: {label}={option}",
            ) from exc
        await self.page.wait_for_timeout(200)

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
                "SRM_STMT_RECEIPTS_EXPORT_UNAVAILABLE",
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
                "SRM_STMT_RECEIPTS_EXPORT_FAILED",
                "Supplier portal receipt list export did not start",
            ) from exc
        name = _clean(getattr(download, "suggested_filename", "")) or artifact_name
        if not name.lower().endswith(".xlsx"):
            raise RpaBusinessError(
                "SRM_STMT_RECEIPTS_EXPORT_INVALID",
                "Supplier portal export is not an XLSX file",
            )
        path = Path(await download.path())
        content = path.read_bytes()
        await self.ctx.artifacts.save_download(download, name, step_id=step_id)
        return content


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")
    raw_input = ctx.input if isinstance(ctx.input, Mapping) else {}
    date_start = _clean(raw_input.get("dateStart") or raw_input.get("date_start"))
    date_end = _clean(raw_input.get("dateEnd") or raw_input.get("date_end"))
    if not date_start or not date_end:
        raise RpaFatalError("STMT_DATE_RANGE_REQUIRED", "dateStart/dateEnd are required")
    parse_ymd(date_start)
    parse_ymd(date_end)

    await ctx.log.info("Starting statement receipt query Flow")
    adapter = ReceiptListAdapter(ctx)
    await adapter.login()
    await adapter.open_receipt_list(date_start, date_end)

    step_id = "srm.query_receipts"
    await _safe_emit(
        ctx,
        "STEP_STARTED",
        message="Searching unsubmitted receipts and exporting Excel",
        payload={"stepId": step_id, "stepType": step_id},
    )
    await _safe_screenshot(ctx, "supplier-portal-receipts", step_id)

    content = None
    if not await adapter.result_is_empty():
        content = await adapter.export_xlsx("receipts.xlsx")
        if content is None:
            raise RpaRetryableError(
                "SRM_STMT_RECEIPTS_EXPORT_UNAVAILABLE",
                "Supplier portal export is disabled for the receipt list",
            )
    raw_rows = read_xlsx_table(content) if content else []
    rows = normalize_receipt_rows(raw_rows)
    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Unsubmitted receipts collected from Excel export",
        payload={
            "stepId": step_id,
            "totalRows": len(rows),
            "sourceFilter": f"{RECONCILE_STATUS_LABEL}={UNSUBMITTED_STATUS}",
        },
    )
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "portalUrl": ctx.portal_url,
        "dateStart": date_start,
        "dateEnd": date_end,
        "queriedAt": date.today().isoformat(),
        "totalRows": len(rows),
        "rows": rows,
        "source": "xlsx",
        "sourceFilter": f"{RECONCILE_STATUS_LABEL}={UNSUBMITTED_STATUS}",
    }
