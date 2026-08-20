import importlib.util
import sys
import unittest
from pathlib import Path

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_fill_line_delivery_date_flow",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

find_line = flow_module.find_line
resolve_captcha_code = flow_module.resolve_captcha_code
validate_input = flow_module.validate_input


class ValidateInputTests(unittest.TestCase):
    def test_valid_input(self):
        po_no, line_no, expected_date = validate_input(
            {
                "po_no": " pojs2607130002 ",
                "line_number": "10",
                "expected_delivery_date": "2026-08-20",
            }
        )
        self.assertEqual(po_no, "POJS2607130002")
        self.assertEqual(line_no, "10")
        self.assertEqual(expected_date, "2026-08-20")

    def test_rejects_missing_po_no(self):
        with self.assertRaises(RpaBusinessError):
            validate_input({"line_number": "10", "expected_delivery_date": "2026-08-20"})

    def test_rejects_missing_line_number(self):
        with self.assertRaises(RpaBusinessError):
            validate_input({"po_no": "POJS2607130002", "expected_delivery_date": "2026-08-20"})

    def test_rejects_bad_date_format(self):
        with self.assertRaises(RpaBusinessError):
            validate_input(
                {
                    "po_no": "POJS2607130002",
                    "line_number": "10",
                    "expected_delivery_date": "2026/08/20",
                }
            )

    def test_rejects_invalid_calendar_date(self):
        with self.assertRaises(RpaBusinessError):
            validate_input(
                {
                    "po_no": "POJS2607130002",
                    "line_number": "10",
                    "expected_delivery_date": "2026-13-40",
                }
            )


class FindLineTests(unittest.TestCase):
    LINES = [
        {"lineNo": "10", "materialNo": "MAT-001", "currentExpectedDate": ""},
        {"lineNo": "20", "materialNo": "MAT-002", "currentExpectedDate": "2026-08-01"},
    ]

    def test_finds_target_line(self):
        line = find_line(self.LINES, "20")
        self.assertEqual(line["materialNo"], "MAT-002")

    def test_missing_line_raises(self):
        with self.assertRaises(RpaBusinessError) as ctx:
            find_line(self.LINES, "30")
        self.assertEqual(ctx.exception.code, "ORDER_LINE_NOT_FOUND")

    def test_duplicate_line_raises(self):
        with self.assertRaises(RpaBusinessError) as ctx:
            find_line(self.LINES + [self.LINES[0]], "10")
        self.assertEqual(ctx.exception.code, "ORDER_LINE_DATA_AMBIGUOUS")

    def test_empty_lines_raises(self):
        with self.assertRaises(RpaBusinessError) as ctx:
            find_line([], "10")
        self.assertEqual(ctx.exception.code, "ORDER_LINES_NOT_FOUND")


class ResolveCaptchaCodeTests(unittest.TestCase):
    def test_resolves_known_filename(self):
        self.assertEqual(resolve_captcha_code("http://x/assets/code03.png"), "sez0")

    def test_unknown_returns_none(self):
        self.assertIsNone(resolve_captcha_code("http://x/assets/code99.png"))


if __name__ == "__main__":
    unittest.main()
