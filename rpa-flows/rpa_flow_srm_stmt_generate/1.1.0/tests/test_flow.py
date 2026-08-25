import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from nodeskclaw_rpa_engine.runtime import RpaFatalError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_stmt_generate_flow_1_1_0",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

generate_result = flow_module.generate_result
parse_lines = flow_module.parse_lines
resolve_check_amount = flow_module.resolve_check_amount
SELECTORS = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))


class FakeLocator:
    def __init__(self, page=None, selector="", *, visible=False, src=None, disabled=False):
        self.page = page
        self.selector = selector
        self.visible = visible
        self.src = src
        self.disabled = disabled

    @property
    def first(self):
        return self

    async def is_visible(self):
        return self.visible

    async def is_disabled(self):
        return self.disabled

    async def wait_for(self, *, state="visible", timeout=0):
        if state == "visible" and not self.visible:
            raise TimeoutError("not visible")
        if state == "hidden" and self.visible:
            raise TimeoutError("still visible")

    async def get_attribute(self, name):
        if name == "class":
            return "el-button is-disabled" if self.disabled else "el-button"
        return self.src

    async def count(self):
        return 1 if self.visible else 0

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

    async def wait_for_timeout(self, ms):
        return


class RecordingEvents:
    def __init__(self):
        self.items = []

    async def emit(self, type, message="", payload=None):
        self.items.append({"type": type, "message": message, "payload": payload or {}})


class ParseLinesTests(unittest.TestCase):
    def test_parse_lines(self):
        lines = parse_lines(
            [
                {"receiptNo": "WR1", "lineNo": "10"},
                {"收货单号": "WR2", "收货单行号": "20"},
            ]
        )
        self.assertEqual(
            lines,
            [
                {"receiptNo": "WR1", "lineNo": "10", "orderNo": ""},
                {"receiptNo": "WR2", "lineNo": "20", "orderNo": ""},
            ],
        )

    def test_empty_raises(self):
        with self.assertRaises(RpaFatalError):
            parse_lines([])

    def test_resolve_amount_from_local(self):
        self.assertEqual(resolve_check_amount({"localAmount": "10.1"}, []), "10.10")


class GenerateResultTests(unittest.TestCase):
    def test_dry_run_does_not_commit(self):
        payload = generate_result(
            dry_run=True,
            check_amount="12.50",
            check_date="2026-08-21",
            line_count=3,
        )
        self.assertFalse(payload["committed"])
        self.assertTrue(payload["dryRun"])
        self.assertEqual(payload["blockedAction"], "generate_statement")
        self.assertTrue(payload["generateButtonFound"])

    def test_live_run_commits(self):
        payload = generate_result(
            dry_run=False,
            check_amount="12.50",
            check_date="2026-08-21",
            line_count=3,
        )
        self.assertTrue(payload["committed"])
        self.assertFalse(payload["dryRun"])
        self.assertNotIn("blockedAction", payload)


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


class LocateGenerateButtonTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_visible_enabled_button_without_clicking(self):
        page = FakePage(
            {
                SELECTORS["generate_button"]: FakeLocator(visible=True, disabled=False),
            }
        )
        adapter = flow_module.ReceiptListAdapter(
            SimpleNamespace(
                artifacts=SimpleNamespace(screenshot=AsyncMock()),
                events=RecordingEvents(),
                page=page,
                portal_url="https://supplier.tiandy.com/",
                selectors=SELECTORS,
            )
        )
        button = await adapter.locate_generate_button()
        self.assertTrue(button.visible)
        self.assertEqual(page.clicks, [])


class OfficialPackageGuardTests(unittest.TestCase):
    def test_manifest_is_1_1_0(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.1.0")

    def test_selectors_have_no_data_rpa(self):
        raw = (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)

    def test_flow_has_no_data_rpa(self):
        raw = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)

    def test_uses_official_route_and_generate_button(self):
        raw = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertIn("#/order/receivingList", raw)
        self.assertIn("is_dry_run", raw)
        self.assertIn("install_write_guard", raw)
        self.assertIn("生成对账单", SELECTORS["generate_button"])


if __name__ == "__main__":
    unittest.main()
