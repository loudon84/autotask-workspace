"""Prove 1.1.0 row selector misses frozen 收货应付; 1.1.1 includes fixed-body-wrapper.

No live portal. Parses a local Element UI-like table.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

FLOW_DIR = Path(__file__).resolve().parents[1]
ENGINE_SRC = Path(__file__).resolve().parents[4] / "rpa-engine" / "src"
sys.path.insert(0, str(ENGINE_SRC))

SPEC = importlib.util.spec_from_file_location(
    "srm_stmt_upload_invoice_flow_1_1_1_click",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

FIXTURE_HTML = """
<div class="el-table">
  <div class="el-table__header-wrapper">
    <table><thead><tr><th>对账日期</th><th>对账总额</th><th>操作</th></tr></thead></table>
  </div>
  <div class="el-table__body-wrapper">
    <table><tbody><tr><td>2026-04-01</td><td>5,768,205.32</td><td></td></tr></tbody></table>
  </div>
  <div class="el-table__fixed-right">
    <div class="el-table__fixed-body-wrapper">
      <table><tbody><tr><td><button class="el-button">收货应付</button></td></tr></tbody></table>
    </div>
  </div>
</div>
"""

OLD_ROW_SELECTOR = r"\.el-table__body-wrapper tbody tr(?!,)"
NEW_ROW_SELECTOR = "el-table__fixed-body-wrapper"


class _ClassCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.fixed_right_has_body_wrapper = False
        self.fixed_right_has_fixed_body = False
        self.payable_in_fixed_right = False
        self._in_fixed_right = 0

    def handle_starttag(self, tag, attrs):
        classes = " ".join(dict(attrs).get("class", "").split())
        self.stack.append(classes)
        if "el-table__fixed-right" in classes.split():
            self._in_fixed_right += 1
        if self._in_fixed_right:
            if "el-table__body-wrapper" in classes.split() and "el-table__fixed-body-wrapper" not in classes.split():
                self.fixed_right_has_body_wrapper = True
            if "el-table__fixed-body-wrapper" in classes.split():
                self.fixed_right_has_fixed_body = True

    def handle_endtag(self, tag):
        if self.stack:
            classes = self.stack.pop()
            if "el-table__fixed-right" in classes.split() and self._in_fixed_right:
                self._in_fixed_right -= 1

    def handle_data(self, data):
        if self._in_fixed_right and "收货应付" in data:
            self.payable_in_fixed_right = True


class FrozenPayableSelectorTests(unittest.TestCase):
    def test_fixture_only_exposes_payable_in_fixed_body_wrapper(self):
        parser = _ClassCollector()
        parser.feed(FIXTURE_HTML)
        self.assertFalse(parser.fixed_right_has_body_wrapper)
        self.assertTrue(parser.fixed_right_has_fixed_body)
        self.assertTrue(parser.payable_in_fixed_right)

    def test_old_package_js_only_queries_body_wrapper(self):
        old = Path(
            FLOW_DIR.parent / "1.1.0" / "flow.py"
        ).read_text(encoding="utf-8")
        click = old.split("CLICK_PAYABLE_JS", 1)[1].split("READ_BASE_INFO_JS", 1)[0]
        self.assertIn(".el-table__body-wrapper tbody tr", click)
        self.assertNotIn("el-table__fixed-body-wrapper", click)

    def test_current_js_queries_fixed_body_wrapper(self):
        self.assertIn("el-table__fixed-body-wrapper", flow_module.CLICK_PAYABLE_JS)
        self.assertIn("el-table__body-wrapper tbody tr, .el-table__fixed-body-wrapper tbody tr", flow_module.CLICK_PAYABLE_JS)

    def test_find_js_still_matches_date_and_amount(self):
        self.assertIn("对账日期", flow_module.FIND_STATEMENT_JS)
        self.assertIn("对账总额", flow_module.FIND_STATEMENT_JS)
        self.assertIn("wantAmount", flow_module.FIND_STATEMENT_JS)
        self.assertIn("matched: true", flow_module.FIND_STATEMENT_JS)


if __name__ == "__main__":
    unittest.main()
