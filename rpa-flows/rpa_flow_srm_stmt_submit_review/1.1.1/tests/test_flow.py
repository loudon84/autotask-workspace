import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from nodeskclaw_rpa_engine.runtime import RpaBusinessError, RpaFatalError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_stmt_submit_review_flow_1_1_1",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

submit_result = flow_module.submit_result
require_match_key = flow_module.require_match_key
ensure_invoice_ready = flow_module.ensure_invoice_ready
describe_not_found = flow_module.describe_not_found
normalize_invoice_no = flow_module.normalize_invoice_no
validate_file_paths = flow_module.validate_file_paths
require_expected_invoice = flow_module.require_expected_invoice
assert_invoice_matches = flow_module.assert_invoice_matches
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


class SubmitHelperTests(unittest.TestCase):
    def test_require_match_key(self):
        self.assertEqual(
            require_match_key({"checkDate": "2026-04-01", "checkAmount": "10.00"}),
            ("2026-04-01", "10.00"),
        )

    def test_require_match_key_missing(self):
        with self.assertRaises(RpaFatalError):
            require_match_key({})

    def test_ensure_invoice_ready(self):
        with self.assertRaises(RpaBusinessError):
            ensure_invoice_ready("", "10")

    def test_describe_not_found_empty(self):
        message = describe_not_found("2026-04-01", "10.00", {"error": "not_found"})
        self.assertIn("列表为空", message)

    def test_normalize_invoice_no_strips_remark_counter(self):
        self.assertEqual(
            normalize_invoice_no("INV_20260818287 备注 0/100"),
            "INV_20260818287",
        )

    def test_validate_file_paths_required(self):
        with self.assertRaises(RpaFatalError):
            validate_file_paths([])

    def test_require_expected_invoice(self):
        self.assertEqual(
            require_expected_invoice(
                {"expectedInvoiceNo": "INV_1", "expectedInvoiceAmount": "10.00"}
            ),
            ("INV_1", "10.00"),
        )

    def test_assert_invoice_matches(self):
        assert_invoice_matches("INV_1", "10.00", "INV_1", "10.0")

    def test_assert_invoice_mismatch(self):
        with self.assertRaises(RpaBusinessError) as ctx:
            assert_invoice_matches("INV_1", "10.00", "INV_2", "10.00")
        self.assertEqual(ctx.exception.code, "STMT_INVOICE_MISMATCH")


class SubmitResultTests(unittest.TestCase):
    def test_dry_run_does_not_commit(self):
        payload = submit_result(
            dry_run=True,
            check_date="2026-04-01",
            check_amount="10.00",
            invoice_no="INV_1",
            invoice_amount="10.00",
            file_count=1,
        )
        self.assertFalse(payload["committed"])
        self.assertTrue(payload["dryRun"])
        self.assertEqual(payload["blockedAction"], "submit_review")
        self.assertTrue(payload["submitButtonFound"])
        self.assertEqual(payload["checkStatus"], "未对账")

    def test_live_run_commits(self):
        payload = submit_result(
            dry_run=False,
            check_date="2026-04-01",
            check_amount="10.00",
            invoice_no="INV_1",
            invoice_amount="10.00",
            file_count=1,
        )
        self.assertTrue(payload["committed"])
        self.assertFalse(payload["dryRun"])
        self.assertNotIn("blockedAction", payload)
        self.assertEqual(payload["checkStatus"], "已对账")


class LocateSubmitButtonTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_visible_enabled_button_without_clicking(self):
        page = FakePage(
            {
                SELECTORS["submit_button"]: FakeLocator(visible=True, disabled=False),
            }
        )
        adapter = flow_module.StatementSubmitAdapter(
            SimpleNamespace(
                artifacts=SimpleNamespace(screenshot=AsyncMock()),
                events=SimpleNamespace(emit=AsyncMock()),
                page=page,
                portal_url="https://supplier.tiandy.com/",
                selectors=SELECTORS,
            )
        )
        button = await adapter.locate_submit_button()
        self.assertTrue(button.visible)
        self.assertEqual(page.clicks, [])


class OfficialPackageGuardTests(unittest.TestCase):
    def test_manifest_is_1_1_1(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.1.1")

    def test_selectors_have_no_data_rpa(self):
        raw = (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)

    def test_flow_has_no_data_rpa(self):
        raw = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)

    def test_uses_official_route_and_submit_button(self):
        raw = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertIn("#/reconciliation/reconciliationStatement", raw)
        self.assertIn("is_dry_run", raw)
        self.assertIn("install_write_guard", raw)
        self.assertIn("assert_invoice_matches", raw)
        self.assertIn("expectedInvoiceNo", raw)
        self.assertIn("提交审核", SELECTORS["submit_button"])
        self.assertNotIn("#/finance/reconciliation", raw)


if __name__ == "__main__":
    unittest.main()
