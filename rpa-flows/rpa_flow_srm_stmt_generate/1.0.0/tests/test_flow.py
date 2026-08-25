import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("srm_stmt_generate_flow", FLOW_DIR / "flow.py")
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

parse_lines = flow_module.parse_lines
resolve_check_amount = flow_module.resolve_check_amount
SELECTORS = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))


class FakeLocator:
    def __init__(self, *, visible=False, src=None, count=None):
        self.visible = visible
        self.src = src
        self._count = 1 if count is None and visible else (0 if count is None else count)

    @property
    def first(self):
        return self

    async def count(self):
        return self._count

    async def is_visible(self):
        return self.visible

    async def wait_for(self, *, state="visible", timeout=0):
        if state == "visible" and not self.visible:
            raise TimeoutError("not visible")

    async def get_attribute(self, name):
        return self.src


class RecordingLocator:
    def __init__(self, selector, timeline, *, count=1, visible=True):
        self.selector = selector
        self.timeline = timeline
        self._count = count
        self.visible = visible

    @property
    def first(self):
        return self

    def locator(self, selector):
        return RecordingLocator(f"{self.selector} >> {selector}", self.timeline, count=self._count, visible=self.visible)

    def filter(self, has=None):
        marker = getattr(has, "selector", has)
        return RecordingLocator(f"{self.selector} >> has={marker}", self.timeline, count=self._count, visible=self.visible)

    async def count(self):
        return self._count

    async def is_visible(self):
        return self.visible

    async def click(self, timeout=None):
        self.timeline.append(self.selector)


class FilterPage:
    def __init__(self, timeline):
        self.timeline = timeline

    def locator(self, selector, has=None):
        loc = RecordingLocator(selector, self.timeline)
        if has is not None:
            return loc.filter(has=has)
        return loc


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


class ParseLinesTests(unittest.TestCase):
    def test_parse_lines(self):
        lines = parse_lines(
            [
                {"receiptNo": "WR1", "lineNo": "10"},
                {"收货单号": "WR2", "收货单行号": "20"},
            ]
        )
        self.assertEqual(lines, [
            {"receiptNo": "WR1", "lineNo": "10", "orderNo": ""},
            {"receiptNo": "WR2", "lineNo": "20", "orderNo": ""},
        ])

    def test_resolve_amount_from_local(self):
        self.assertEqual(resolve_check_amount({"localAmount": "10.1"}, []), "10.10")


class LoginReuseTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_an_authenticated_browser_session(self):
        page = FakePage(
            {
                SELECTORS["login_success"]: FakeLocator(visible=True),
                SELECTORS["captcha_image"]: FakeLocator(visible=False),
            }
        )
        adapter = flow_module.StatementGenerateAdapter(
            SimpleNamespace(
                credentials={"username": "portal-user", "password": "secret"},
                page=page,
                portal_url="http://portal.test/",
                selectors=SELECTORS,
            )
        )

        await adapter.login()

        self.assertEqual(page.gotos, [])
        self.assertEqual(page.fills, [])


class RowCheckboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_clicks_selection_checkbox_on_the_marker_row(self):
        timeline = []
        adapter = flow_module.StatementGenerateAdapter(
            SimpleNamespace(page=FilterPage(timeline), selectors=SELECTORS)
        )

        row = adapter._row_locator("POJS2604230001", "10")
        await adapter._check_row(row)

        self.assertEqual(
            timeline,
            [
                ".el-table__body-wrapper tbody tr >> has=[data-rpa='receiving-row-POJS2604230001-10'] >> td.el-table-column--selection .el-checkbox"
            ],
        )


if __name__ == "__main__":
    unittest.main()
