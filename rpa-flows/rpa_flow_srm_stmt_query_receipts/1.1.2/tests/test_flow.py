import importlib.util
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape

from nodeskclaw_rpa_engine.runtime import RpaBusinessError, RpaFatalError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_stmt_query_receipts_flow_1_1_2",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

excel_serial_to_date = flow_module.excel_serial_to_date
month_nav_action = flow_module.month_nav_action
normalize_receipt_rows = flow_module.normalize_receipt_rows
parse_ymd = flow_module.parse_ymd
read_xlsx_table = flow_module.read_xlsx_table
resolve_captcha_code = flow_module.resolve_captcha_code
SELECTORS = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))


class FakeLocator:
    def __init__(self, page=None, selector="", *, visible=False, src=None, count=1):
        self.page = page
        self.selector = selector
        self.visible = visible
        self.src = src
        self._count = count

    @property
    def first(self):
        return self

    async def is_visible(self):
        return self.visible

    async def wait_for(self, *, state="visible", timeout=0):
        if state == "visible" and not self.visible:
            raise TimeoutError("not visible")
        if state == "hidden" and self.visible:
            raise TimeoutError("still visible")

    async def get_attribute(self, name):
        return self.src

    async def count(self):
        return self._count if self.visible else 0

    async def click(self, timeout=0):
        if self.page is not None:
            self.page.clicks.append(self.selector)


class FakePage:
    def __init__(self, locators):
        self._locators = locators
        self.gotos = []
        self.fills = []
        self.clicks = []

    async def goto(self, url, wait_until=None):
        self.gotos.append(url)

    def locator(self, selector):
        existing = self._locators.get(selector)
        if existing is not None:
            existing.page = self
            existing.selector = selector
            return existing
        return FakeLocator(self, selector)

    async def fill(self, selector, value):
        self.fills.append((selector, value))

    async def click(self, selector):
        self.clicks.append(selector)

    async def wait_for_timeout(self, ms):
        return


class RecordingEvents:
    def __init__(self):
        self.items = []

    async def emit(self, type, message="", payload=None):
        self.items.append({"type": type, "message": message, "payload": payload or {}})


def column_name(index):
    value = ""
    remaining = index + 1
    while remaining:
        remaining, current = divmod(remaining - 1, 26)
        value = chr(65 + current) + value
    return value


def make_xlsx(headers, rows=None):
    rows = rows or []
    values = []
    indexes = {}
    for value in [*headers, *(item for row in rows for item in row)]:
        text = str(value)
        if text not in indexes:
            indexes[text] = len(values)
            values.append(text)
    shared = "".join(f"<si><t>{escape(value)}</t></si>" for value in values)

    def xml_row(number, row):
        cells = "".join(
            (
                f'<c r="{column_name(index)}{number}" '
                f't="s"><v>{indexes[str(value)]}</v></c>'
            )
            for index, value in enumerate(row)
        )
        return f'<row r="{number}">{cells}</row>'

    sheet_rows = xml_row(1, headers) + "".join(
        xml_row(index + 2, row) for index, row in enumerate(rows)
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{shared}</sst>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<workbook "
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="sheet1" sheetId="1" '
            'r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Relationships "
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<worksheet "
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{sheet_rows}</sheetData></worksheet>",
        )
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Types "
            'xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Relationships "
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        )
    return output.getvalue()


class ParseDateTests(unittest.TestCase):
    def test_parses_ymd(self):
        self.assertEqual(parse_ymd("2026-08-01").isoformat(), "2026-08-01")

    def test_rejects_datetime(self):
        with self.assertRaises(RpaFatalError):
            parse_ymd("2026-08-01 00:00:00")

    def test_rejects_invalid_day(self):
        with self.assertRaises(RpaFatalError):
            parse_ymd("2026-02-31")


class MonthNavTests(unittest.TestCase):
    def test_same_month_is_left(self):
        self.assertEqual(month_nav_action(2026, 8, 2026, 8, 2026, 9), "visible-left")

    def test_right_panel_month(self):
        self.assertEqual(month_nav_action(2026, 8, 2026, 9, 2026, 9), "visible-right")

    def test_earlier_month_uses_prev(self):
        self.assertEqual(month_nav_action(2026, 8, 2026, 4, 2026, 9), "month-prev")

    def test_earlier_year_uses_year_prev(self):
        self.assertEqual(month_nav_action(2026, 8, 2025, 8, 2026, 9), "year-prev")

    def test_later_month_uses_next(self):
        self.assertEqual(month_nav_action(2026, 8, 2026, 11, 2026, 9), "month-next")


class NormalizeReceiptRowsTests(unittest.TestCase):
    def test_maps_chinese_headers_and_dedupes(self):
        rows = normalize_receipt_rows(
            [
                {
                    "收货单号": "WRJS2608140059",
                    "收货单行号": "10",
                    "订单编号": "POJS2607130002",
                    "可立账价税合计（元）": "689824.51",
                    "对账状态": "未提交",
                },
                {
                    "收货单号": "WRJS2608140059",
                    "收货单行号": "10",
                    "可立账价税合计（元）": "689824.51",
                },
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["receiptNo"], "WRJS2608140059")
        self.assertEqual(rows[0]["lineNo"], "10")
        self.assertEqual(rows[0]["taxIncludedAmount"], "689824.51")

    def test_maps_demo_amount_header(self):
        rows = normalize_receipt_rows(
            [
                {
                    "收货单号": "WR1",
                    "行号": "10",
                    "价税合计": "5,999.74",
                    "对账状态": "未提交",
                }
            ]
        )
        self.assertEqual(rows[0]["taxIncludedAmount"], "5999.74")
        self.assertEqual(rows[0]["lineNo"], "10")

    def test_converts_excel_serial_inbound_date(self):
        serial = excel_serial_to_date("46235")
        rows = normalize_receipt_rows(
            [
                {
                    "收货单号": "WR1",
                    "收货单行号": "10",
                    "对账状态": "未提交",
                    "入库确认日期": "46235",
                    "可立账价税合计（元）": "1",
                }
            ]
        )
        self.assertEqual(rows[0]["inboundConfirmDate"], serial)
        self.assertRegex(rows[0]["inboundConfirmDate"], r"^2026-")

    def test_skips_incomplete_rows(self):
        rows = normalize_receipt_rows([{"收货单号": "WR1"}, {"收货单行号": "10"}])
        self.assertEqual(rows, [])

    def test_non_list_raises(self):
        with self.assertRaises(RpaBusinessError):
            normalize_receipt_rows(None)


class XlsxTests(unittest.TestCase):
    def test_reads_header_rows(self):
        content = make_xlsx(
            ["收货单号", "收货单行号", "对账状态", "可立账价税合计（元）"],
            [["WR1", "10", "未提交", "12.5"]],
        )
        records = read_xlsx_table(content)
        rows = normalize_receipt_rows(records)
        self.assertEqual(rows[0]["receiptNo"], "WR1")
        self.assertEqual(rows[0]["taxIncludedAmount"], "12.5")


class CaptchaTests(unittest.TestCase):
    def test_known_code(self):
        self.assertEqual(resolve_captcha_code("/assets/code01.png"), "mp3s")


class LoginReuseTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_an_authenticated_browser_session(self):
        page = FakePage(
            {
                SELECTORS["login_success"]: FakeLocator(visible=True),
                SELECTORS["captcha_image"]: FakeLocator(visible=False),
            }
        )
        adapter = flow_module.ReceiptListAdapter(
            SimpleNamespace(
                credentials={"username": "portal-user", "password": "secret"},
                events=RecordingEvents(),
                page=page,
                portal_url="https://supplier.tiandy.com/",
                selectors=SELECTORS,
            )
        )

        await adapter.login()

        self.assertEqual(page.gotos, [])
        self.assertEqual(page.fills, [])


class OpenReceiptListTests(unittest.IsolatedAsyncioTestCase):
    async def test_opens_official_receiving_list_route(self):
        page = FakePage(
            {
                SELECTORS["receipt_page"]: FakeLocator(visible=True),
            }
        )
        page.keyboard = SimpleNamespace(press=lambda key: None)

        adapter = flow_module.ReceiptListAdapter(
            SimpleNamespace(
                events=RecordingEvents(),
                page=page,
                portal_url="https://supplier.tiandy.com/#/login",
                selectors=SELECTORS,
            )
        )

        async def skip_dates(date_start, date_end):
            return None

        async def skip_filter(label, option):
            return None

        async def skip_wait():
            return None

        adapter.pick_inbound_confirm_range = skip_dates
        adapter.select_form_option = skip_filter
        adapter._wait_loading_done = skip_wait
        await adapter.open_receipt_list("2026-08-01", "2026-08-01")
        self.assertEqual(
            page.gotos, ["https://supplier.tiandy.com/#/order/receivingList"]
        )
        self.assertIn(SELECTORS["search_button"], page.clicks)


class OfficialPackageGuardTests(unittest.TestCase):
    def test_manifest_is_1_1_2(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.1.2")
        self.assertIn("DOWNLOAD", manifest["capabilities"])

    def test_selectors_have_no_data_rpa(self):
        raw = (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)

    def test_flow_has_no_data_rpa(self):
        raw = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)

    def test_selectors_use_official_picker(self):
        self.assertIn("入库确认", SELECTORS["date_range"])
        self.assertIn("el-date-range-picker", SELECTORS["date_picker"])
        self.assertIn("确定", SELECTORS["date_picker_confirm"])
        self.assertIn("导出", SELECTORS["export_button"])


if __name__ == "__main__":
    unittest.main()
