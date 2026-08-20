import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_stmt_query_receipts_flow_1_1_0",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

normalize_receipt_rows = flow_module.normalize_receipt_rows
resolve_captcha_code = flow_module.resolve_captcha_code
SELECTORS = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))


class FakeLocator:
    def __init__(self, *, visible=False, src=None):
        self.visible = visible
        self.src = src

    async def is_visible(self):
        return self.visible

    async def wait_for(self, *, state="visible", timeout=0):
        if state == "visible" and not self.visible:
            raise TimeoutError("not visible")

    async def get_attribute(self, name):
        return self.src


class FakePage:
    def __init__(self, locators):
        self._locators = locators
        self.gotos = []
        self.fills = []

    async def goto(self, url, wait_until=None):
        self.gotos.append(url)

    def locator(self, selector):
        return self._locators.get(selector, FakeLocator())

    async def fill(self, selector, value):
        self.fills.append((selector, value))

    async def click(self, selector):
        return

    async def wait_for_timeout(self, ms):
        return


class RecordingEvents:
    def __init__(self):
        self.items = []

    async def emit(self, type, message="", payload=None):
        self.items.append({"type": type, "message": message, "payload": payload or {}})


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

    def test_skips_incomplete_rows(self):
        rows = normalize_receipt_rows([{"收货单号": "WR1"}, {"收货单行号": "10"}])
        self.assertEqual(rows, [])

    def test_non_list_raises(self):
        with self.assertRaises(RpaBusinessError):
            normalize_receipt_rows(None)


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

        async def click(selector):
            page.clicks.append(selector)

        async def press(key):
            return None

        page.keyboard = SimpleNamespace(press=press)

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

        adapter._fill_date_range = skip_dates
        await adapter.open_receipt_list("2026-07-01", "2026-07-31")
        self.assertEqual(
            page.gotos, ["https://supplier.tiandy.com/#/order/receivingList"]
        )


class OfficialPackageGuardTests(unittest.TestCase):
    def test_manifest_is_1_1_0(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.1.0")

    def test_selectors_have_no_data_rpa(self):
        raw = (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)

    def test_collect_js_has_no_data_rpa(self):
        self.assertNotIn("data-rpa", flow_module.COLLECT_RECEIPTS_JS)


if __name__ == "__main__":
    unittest.main()
