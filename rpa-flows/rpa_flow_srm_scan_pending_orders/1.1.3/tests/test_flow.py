import importlib.util
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_scan_pending_orders_flow_1_1_3",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

filter_pending_orders = flow_module.filter_pending_orders
orders_from_export_rows = flow_module.orders_from_export_rows
read_xlsx_table = flow_module.read_xlsx_table
resolve_captcha_code = flow_module.resolve_captcha_code
resolve_searches = flow_module.resolve_searches

HEADERS = ["订单编号", "日期", "订单类型", "总金额(元)", "回复状态", "交货状态", "供应商单位"]


def column_name(index):
    value = ""
    remaining = index + 1
    while remaining:
        remaining, current = divmod(remaining - 1, 26)
        value = chr(65 + current) + value
    return value


def make_xlsx(headers=HEADERS, rows=None):
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
            'Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{sheet_rows}</sheetData></worksheet>",
        )
    return output.getvalue()


class ResolveCaptchaCodeTests(unittest.TestCase):
    def test_resolves_known_filename(self):
        self.assertEqual(resolve_captcha_code("http://x/assets/code01.png"), "mp3s")

    def test_unknown_returns_none(self):
        self.assertIsNone(resolve_captcha_code("http://x/assets/code99.png"))
        self.assertIsNone(resolve_captcha_code(""))


class ResolveSearchesTests(unittest.TestCase):
    def test_missing_config_is_pending_only(self):
        self.assertEqual(
            resolve_searches(None, None),
            [{"replyStatus": "待签章"}],
        )
        self.assertEqual(
            resolve_searches({}, {}),
            [{"replyStatus": "待签章"}],
        )

    def test_binding_searches_win(self):
        searches = resolve_searches(
            {
                "searches": [
                    {"replyStatus": "待签章"},
                    {"poNo": "pojs1", "treatAsPending": True},
                ]
            },
            {"assumedPendingPo": "IGNORED"},
        )
        self.assertEqual(
            searches,
            [
                {"replyStatus": "待签章"},
                {"poNo": "POJS1", "treatAsPending": True},
            ],
        )

    def test_empty_searches_is_pending_only(self):
        self.assertEqual(
            resolve_searches({"searches": []}, None),
            [{"replyStatus": "待签章"}],
        )

    def test_assumed_pending_po_legacy_input(self):
        self.assertEqual(
            resolve_searches(None, {"assumedPendingPo": "pojs1"}),
            [
                {"replyStatus": "待签章"},
                {"poNo": "POJS1", "treatAsPending": True},
            ],
        )

    def test_empty_assumed_pending_po_disables_fallback(self):
        self.assertEqual(
            resolve_searches(None, {"assumedPendingPo": ""}),
            [{"replyStatus": "待签章"}],
        )


class FilterPendingOrdersTests(unittest.TestCase):
    def test_keeps_only_pending_signature_orders(self):
        rows = [
            {"poNo": "POJS2607130002", "replyStatus": "待签章", "orderDate": "2026-07-13"},
            {"poNo": "POJS2606030010", "replyStatus": "待回签"},
            {"poNo": "POJS2604230015", "replyStatus": "已回签"},
        ]
        orders = filter_pending_orders(rows)
        self.assertEqual([order["poNo"] for order in orders], ["POJS2607130002"])

    def test_empty_result(self):
        self.assertEqual(filter_pending_orders([]), [])

    def test_non_list_raises_business_error(self):
        with self.assertRaises(RpaBusinessError):
            filter_pending_orders(None)


class ExcelExportTests(unittest.TestCase):
    def test_reads_pending_rows_from_xlsx(self):
        content = make_xlsx(
            rows=[
                ["POJS2607130002", "2026-07-13", "普通订单", "1", "待签章", "未发货", "芯云"],
                ["POJS2607170008", "2026-07-17", "普通订单", "2", "已回签", "未发货", "芯云"],
            ]
        )
        records = read_xlsx_table(content)
        orders = orders_from_export_rows(records, treat_as_pending=False)
        self.assertEqual([order["poNo"] for order in orders], ["POJS2607130002"])
        self.assertEqual(orders[0]["replyStatus"], "待签章")

    def test_drill_export_treats_signed_row_as_pending(self):
        content = make_xlsx(
            rows=[
                ["POJS2607170008", "2026-07-17", "普通订单", "36867287.81", "已回签", "未发货", "芯云"],
            ]
        )
        records = read_xlsx_table(content)
        orders = orders_from_export_rows(records, treat_as_pending=True)
        self.assertEqual(orders[0]["poNo"], "POJS2607170008")
        self.assertEqual(orders[0]["replyStatus"], "待签章")
        self.assertEqual(orders[0]["totalAmount"], "36867287.81")

    def test_empty_workbook_returns_no_orders(self):
        content = make_xlsx(rows=[])
        self.assertEqual(read_xlsx_table(content), [])
        self.assertEqual(orders_from_export_rows([], treat_as_pending=False), [])

    def test_rejects_non_xlsx_bytes(self):
        with self.assertRaises(RpaBusinessError):
            read_xlsx_table(b"not-xlsx")


class OfficialPackageGuardTests(unittest.TestCase):
    def test_manifest_is_1_1_3(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.1.3")
        self.assertIn("DOWNLOAD", manifest["capabilities"])
        names = {field["name"] for field in manifest["inputSchema"]}
        self.assertNotIn("assumedPendingPo", names)

    def test_login_does_not_wait_for_human(self):
        source = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertIn("login_official_srm", source)
        self.assertNotIn("HUMAN_VERIFICATION_REQUIRED", source)
        self.assertIn("导出", source)
        self.assertIn("expect_download", source)
        self.assertNotIn("DEFAULT_DRILL_PO", source)
        self.assertIn("resolve_searches", source)

    def test_selectors_have_no_data_rpa(self):
        raw = (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)
        selectors = json.loads(raw)
        self.assertIn("导出", selectors["export_button"])
        self.assertIn("查询", selectors["search_button"])

    def test_does_not_scrape_table_for_orders(self):
        source = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertNotIn("COLLECT_ORDERS_JS", source)


if __name__ == "__main__":
    unittest.main()
