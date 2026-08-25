import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_check_reply_status_flow_1_1_4",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

validate_input = flow_module.validate_input
resolve_captcha_code = flow_module.resolve_captcha_code
SELECTORS = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))


class FakeLocator:
    def __init__(self, *, visible=False, text="", count=1):
        self.visible = visible
        self.text = text
        self._count = count
        self.clicks = 0

    async def is_visible(self):
        return self.visible

    async def wait_for(self, *, state="visible", timeout=0):
        if state == "visible" and not self.visible:
            raise TimeoutError("not visible")

    async def get_attribute(self, name):
        return None

    async def inner_text(self):
        return self.text

    async def count(self):
        return self._count

    async def click(self, timeout=None, force=None):  # noqa: ANN001
        self.clicks += 1

    def get_by_text(self, text, exact=False):  # noqa: ANN001
        return self

    def locator(self, selector):  # noqa: ANN001
        return self

    def filter(self, has_text=None, has=None):  # noqa: ANN001
        return self

    @property
    def first(self):
        return self

    def nth(self, index):
        return self


class FakePage:
    def __init__(self, locators, *, evaluate_result=True):
        self._locators = locators
        self.gotos = []
        self.fills = []
        self.clicks = []
        self.evaluates = []
        self.evaluate_result = evaluate_result
        self.keyboard = SimpleNamespace(press=self._press)

    async def _press(self, key):
        return None

    async def goto(self, url, wait_until=None):
        self.gotos.append(url)

    def locator(self, selector, **kwargs):  # noqa: ANN003
        return self._locators.get(selector, FakeLocator())

    async def fill(self, selector, value):
        self.fills.append((selector, value))

    async def click(self, selector):
        self.clicks.append(selector)

    async def wait_for_timeout(self, ms):
        return

    async def evaluate(self, script, arg=None):
        self.evaluates.append(arg)
        return self.evaluate_result

    def get_by_text(self, text, exact=False):  # noqa: ANN001
        return self._locators.get(f"text={text}", FakeLocator(visible=True))


class RecordingEvents:
    def __init__(self):
        self.items = []

    async def emit(self, type, message="", payload=None, level=None):
        self.items.append({"type": type, "message": message, "payload": payload or {}})


class ValidateInputTests(unittest.TestCase):
    def test_valid_input(self):
        self.assertEqual(validate_input({"po_no": " pojs2607130002 "}), "POJS2607130002")

    def test_rejects_missing_po_no(self):
        with self.assertRaises(RpaBusinessError):
            validate_input({})
        with self.assertRaises(RpaBusinessError):
            validate_input(None)


class CaptchaTests(unittest.TestCase):
    def test_known_captcha(self):
        self.assertEqual(resolve_captcha_code("/assets/code01.png"), "mp3s")

    def test_data_url_returns_none(self):
        self.assertIsNone(resolve_captcha_code("data:image/png;base64,abc"))


class OfficialPackageGuardTests(unittest.TestCase):
    def test_manifest_is_1_1_4(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.1.4")
        selectors = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))
        self.assertIn("查看签章", selectors["detail_page"])
        self.assertNotIn("reply_status", selectors)
        self.assertNotIn(".el-drawer", selectors["detail_page"])
        source = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertIn("回复状态", source)
        self.assertIn("已回签", source)

    def test_selectors_have_no_data_rpa(self):
        raw = (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)


class OpenOrderDetailTests(unittest.IsolatedAsyncioTestCase):
    async def test_marks_row_and_clicks_detail(self):
        po_no = "POJS2607170008"
        locators = {
            SELECTORS["order_page"]: FakeLocator(visible=True),
            SELECTORS["loading_mask"]: FakeLocator(visible=False),
            SELECTORS["order_row"].replace("{po_no}", po_no): FakeLocator(visible=True),
            SELECTORS["detail_page"]: FakeLocator(visible=True),
        }
        page = FakePage(locators)
        adapter = flow_module.SupplierPortalReplyStatusAdapter(
            SimpleNamespace(
                events=RecordingEvents(),
                page=page,
                portal_url="https://supplier.tiandy.com/#/login",
                selectors=SELECTORS,
            )
        )

        await adapter.open_order_detail(po_no)

        self.assertEqual(page.gotos, ["https://supplier.tiandy.com/#/order/list"])
        self.assertEqual(page.fills, [(SELECTORS["po_number"], po_no)])
        self.assertIn(SELECTORS["search_button"], page.clicks)
        self.assertEqual(page.evaluates, [po_no])
        self.assertEqual(await adapter.reply_status(), "已回签")

    async def test_missing_signed_row_is_unsigned(self):
        po_no = "POJS2607170008"
        page = FakePage(
            {
                SELECTORS["order_page"]: FakeLocator(visible=True),
                SELECTORS["loading_mask"]: FakeLocator(visible=False),
                SELECTORS["order_row"].replace("{po_no}", po_no): FakeLocator(
                    visible=False, count=0
                ),
                ".el-table__body-wrapper tbody tr": FakeLocator(visible=False, count=0),
            },
            evaluate_result=False,
        )
        adapter = flow_module.SupplierPortalReplyStatusAdapter(
            SimpleNamespace(
                events=RecordingEvents(),
                page=page,
                portal_url="https://supplier.tiandy.com/",
                selectors=SELECTORS,
            )
        )
        await adapter.open_order_detail(po_no)
        self.assertEqual(await adapter.reply_status(), "待回签")


class ReplyStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_opened_detail_is_signed(self):
        adapter = flow_module.SupplierPortalReplyStatusAdapter(
            SimpleNamespace(
                events=RecordingEvents(),
                page=FakePage({}),
                portal_url="https://supplier.tiandy.com/",
                selectors=SELECTORS,
            )
        )
        adapter._reply_status = "已回签"
        self.assertEqual(await adapter.reply_status(), "已回签")

    async def test_missing_search_hit_is_unsigned(self):
        adapter = flow_module.SupplierPortalReplyStatusAdapter(
            SimpleNamespace(
                events=RecordingEvents(),
                page=FakePage({}),
                portal_url="https://supplier.tiandy.com/",
                selectors=SELECTORS,
            )
        )
        adapter._reply_status = "待回签"
        self.assertEqual(await adapter.reply_status(), "待回签")


class RunFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_returns_reply_status_without_signing(self):
        adapter = SimpleNamespace(
            login=AsyncMock(),
            open_order_detail=AsyncMock(),
            reply_status=AsyncMock(return_value="已回签"),
        )
        original = flow_module.SupplierPortalReplyStatusAdapter
        flow_module.SupplierPortalReplyStatusAdapter = lambda ctx: adapter
        try:
            result = await flow_module.run(
                SimpleNamespace(
                    input={"po_no": "POJS2607170008"},
                    portal_url="https://supplier.tiandy.com/#/login",
                    log=SimpleNamespace(info=AsyncMock()),
                    events=SimpleNamespace(emit=AsyncMock()),
                )
            )
        finally:
            flow_module.SupplierPortalReplyStatusAdapter = original

        self.assertEqual(result["schemaVersion"], "SRM_CHECK_REPLY_STATUS_OUTPUT_V1")
        self.assertEqual(result["poNo"], "POJS2607170008")
        self.assertEqual(result["replyStatus"], "已回签")
        adapter.login.assert_awaited_once()
        adapter.open_order_detail.assert_awaited_once_with("POJS2607170008")
        adapter.reply_status.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
