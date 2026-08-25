import importlib.util
import sys
import unittest
from pathlib import Path

from nodeskclaw_rpa_engine.runtime import RpaBusinessError, RpaFatalError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("srm_stmt_submit_review_flow", FLOW_DIR / "flow.py")
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

require_match_key = flow_module.require_match_key
ensure_invoice_ready = flow_module.ensure_invoice_ready
describe_not_found = flow_module.describe_not_found
normalize_invoice_no = flow_module.normalize_invoice_no
validate_file_paths = flow_module.validate_file_paths


class SubmitReviewHelpersTests(unittest.TestCase):
    def test_require_match_key(self):
        self.assertEqual(
            require_match_key({"checkDate": "2026-08-17", "checkAmount": "10.00"}),
            ("2026-08-17", "10.00"),
        )

    def test_require_match_key_missing(self):
        with self.assertRaises(RpaFatalError):
            require_match_key({})

    def test_ensure_invoice_ready(self):
        with self.assertRaises(RpaBusinessError):
            ensure_invoice_ready("", "10")

    def test_describe_not_found_empty(self):
        message = describe_not_found("2026-08-18", "10.00", {"error": "not_found"})
        self.assertIn("列表为空", message)

    def test_normalize_invoice_no_strips_remark_counter(self):
        self.assertEqual(
            normalize_invoice_no("INV_20260818287 备注 0/100"),
            "INV_20260818287",
        )

    def test_validate_file_paths_required(self):
        with self.assertRaises(RpaFatalError):
            validate_file_paths([])


if __name__ == "__main__":
    unittest.main()
