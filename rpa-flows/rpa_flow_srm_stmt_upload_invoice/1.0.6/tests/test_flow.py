import importlib.util
import sys
import unittest
from pathlib import Path

from nodeskclaw_rpa_engine.runtime import RpaFatalError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("srm_stmt_upload_invoice_flow", FLOW_DIR / "flow.py")
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

validate_file_paths = flow_module.validate_file_paths
describe_not_found = flow_module.describe_not_found
normalize_invoice_no = flow_module.normalize_invoice_no
normalize_invoice_amount = flow_module.normalize_invoice_amount


class ValidateFilePathsTests(unittest.TestCase):
    def test_ok(self):
        paths = validate_file_paths(["a.pdf", "b.png"])
        self.assertEqual(len(paths), 2)

    def test_reject_type(self):
        with self.assertRaises(RpaFatalError):
            validate_file_paths(["a.txt"])

    def test_reject_empty(self):
        with self.assertRaises(RpaFatalError):
            validate_file_paths([])

    def test_describe_not_found_empty(self):
        message = describe_not_found("2026-08-18", "1151309.12", {"error": "not_found"})
        self.assertIn("2026-08-18", message)
        self.assertIn("1151309.12", message)
        self.assertIn("列表为空", message)

    def test_describe_not_found_with_samples(self):
        message = describe_not_found(
            "2026-08-18",
            "1151309.12",
            {
                "samples": [
                    {"date": "2026-08-03", "amount": "16,621,244.11"},
                    {"date": "2026-07-01", "amount": "7,766,226.36"},
                ]
            },
        )
        self.assertIn("2026-08-03/16,621,244.11", message)

    def test_normalize_invoice_no_strips_remark_counter(self):
        self.assertEqual(
            normalize_invoice_no("INV_20260818287 备注 0/100"),
            "INV_20260818287",
        )
        self.assertEqual(normalize_invoice_no("0/100"), "")
        self.assertEqual(normalize_invoice_no("请输入备注 0/100"), "")

    def test_normalize_invoice_amount_strips_following_labels(self):
        self.assertEqual(
            normalize_invoice_amount("1151309.12 最后入库时间 2026-04-30"),
            "1151309.12",
        )


if __name__ == "__main__":
    unittest.main()
