import importlib.util
import sys
import unittest
from pathlib import Path

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_sign_order_flow",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

ensure_all_dates_filled = flow_module.ensure_all_dates_filled
resolve_captcha_code = flow_module.resolve_captcha_code
validate_input = flow_module.validate_input


class ValidateInputTests(unittest.TestCase):
    def test_valid_input(self):
        po_no, backfill = validate_input({"po_no": " pojs2607130002 "})
        self.assertEqual(po_no, "POJS2607130002")
        self.assertEqual(backfill, [])

    def test_rejects_missing_po_no(self):
        with self.assertRaises(RpaBusinessError):
            validate_input({})
        with self.assertRaises(RpaBusinessError):
            validate_input(None)

    def test_rejects_invalid_po_no(self):
        with self.assertRaises(RpaBusinessError):
            validate_input({"po_no": "非法 单号!"})

    def test_temp_backfill_lines(self):
        po_no, backfill = validate_input(
            {
                "po_no": "POJS2607180002",
                "temp_e2e_backfill_dates": True,
                "order_lines": [
                    {"line_number": "10", "expected_delivery_date": "2026-09-15"},
                    {"line_number": "20", "expected_delivery_date": "2026-09-20"},
                ],
            }
        )
        self.assertEqual(po_no, "POJS2607180002")
        self.assertEqual(len(backfill), 2)
        self.assertEqual(backfill[0]["lineNo"], "10")


class EnsureAllDatesFilledTests(unittest.TestCase):
    def test_all_filled_returns_lines(self):
        lines = ensure_all_dates_filled(
            [
                {"lineNo": "10", "materialNo": "MAT-001", "currentExpectedDate": "2026-08-10"},
                {"lineNo": "20", "materialNo": "MAT-002", "currentExpectedDate": "2026-08-12"},
            ]
        )
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["expectedDeliveryDate"], "2026-08-10")

    def test_missing_date_raises_with_line_numbers(self):
        with self.assertRaises(RpaBusinessError) as ctx:
            ensure_all_dates_filled(
                [
                    {"lineNo": "10", "materialNo": "MAT-001", "currentExpectedDate": "2026-08-10"},
                    {"lineNo": "20", "materialNo": "MAT-002", "currentExpectedDate": ""},
                ]
            )
        self.assertEqual(ctx.exception.code, "ORDER_DATES_INCOMPLETE")
        self.assertEqual(ctx.exception.details["missingLineNumbers"], ["20"])

    def test_empty_lines_raises(self):
        with self.assertRaises(RpaBusinessError) as ctx:
            ensure_all_dates_filled([])
        self.assertEqual(ctx.exception.code, "ORDER_LINES_NOT_FOUND")

    def test_missing_line_identity_raises(self):
        with self.assertRaises(RpaBusinessError) as ctx:
            ensure_all_dates_filled([{"lineNo": "", "currentExpectedDate": "2026-08-10"}])
        self.assertEqual(ctx.exception.code, "ORDER_LINE_DATA_AMBIGUOUS")


class ResolveCaptchaCodeTests(unittest.TestCase):
    def test_resolves_known_filename(self):
        self.assertEqual(resolve_captcha_code("http://x/assets/code10.png"), "gqcy")

    def test_unknown_returns_none(self):
        self.assertIsNone(resolve_captcha_code("http://x/assets/code99.png"))


if __name__ == "__main__":
    unittest.main()
