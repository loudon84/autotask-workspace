import importlib.util
import sys
import unittest
from pathlib import Path

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_scan_pending_orders_flow",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

filter_pending_orders = flow_module.filter_pending_orders
resolve_captcha_code = flow_module.resolve_captcha_code


class ResolveCaptchaCodeTests(unittest.TestCase):
    def test_resolves_known_filename(self):
        self.assertEqual(resolve_captcha_code("http://x/assets/code01.png"), "mp3s")
        self.assertEqual(resolve_captcha_code("/static/CODE05.PNG?v=1"), "rpyt")

    def test_unknown_returns_none(self):
        self.assertIsNone(resolve_captcha_code("http://x/assets/code99.png"))
        self.assertIsNone(resolve_captcha_code(None))
        self.assertIsNone(resolve_captcha_code(""))


class FilterPendingOrdersTests(unittest.TestCase):
    def test_keeps_only_pending_signature_orders(self):
        rows = [
            {"poNo": "POJS2607130002", "replyStatus": "待签章", "orderDate": "2026-07-13"},
            {"poNo": "POJS2606030010", "replyStatus": "待回签"},
            {"poNo": "POJS2604230015", "replyStatus": "已回签"},
            {"poNo": "POJS2604230014", "replyStatus": "退回"},
        ]
        orders = filter_pending_orders(rows)
        self.assertEqual([order["poNo"] for order in orders], ["POJS2607130002"])
        self.assertEqual(orders[0]["replyStatus"], "待签章")

    def test_normalizes_po_no_and_deduplicates(self):
        rows = [
            {"poNo": " pojs2607130002 ", "replyStatus": "待签章"},
            {"poNo": "POJS2607130002", "replyStatus": "待签章"},
        ]
        orders = filter_pending_orders(rows)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["poNo"], "POJS2607130002")

    def test_skips_rows_without_po_no(self):
        rows = [
            {"poNo": "", "replyStatus": "待签章"},
            "not-a-mapping",
            {"poNo": "POJS2607170001", "replyStatus": "待签章"},
        ]
        orders = filter_pending_orders(rows)
        self.assertEqual([order["poNo"] for order in orders], ["POJS2607170001"])

    def test_empty_result(self):
        self.assertEqual(filter_pending_orders([]), [])

    def test_non_list_raises_business_error(self):
        with self.assertRaises(RpaBusinessError):
            filter_pending_orders(None)


if __name__ == "__main__":
    unittest.main()
