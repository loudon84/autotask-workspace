import importlib.util
import json
import sys
import unittest
from pathlib import Path

from nodeskclaw_rpa_engine.runtime import RpaFatalError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_stmt_upload_invoice_flow_1_1_1",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

upload_result = flow_module.upload_result
require_match_key = flow_module.require_match_key
validate_file_paths = flow_module.validate_file_paths
SELECTORS = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))


class UploadHelperTests(unittest.TestCase):
    def test_require_match_key(self):
        self.assertEqual(
            require_match_key({"checkDate": "2026-04-01", "checkAmount": "10.00"}),
            ("2026-04-01", "10.00"),
        )

    def test_validate_file_paths_required(self):
        with self.assertRaises(RpaFatalError):
            validate_file_paths([])

    def test_upload_result_does_not_submit(self):
        payload = upload_result(
            check_date="2026-04-01",
            check_amount="10.00",
            invoice_no="INV_1",
            invoice_amount="10.00",
            file_count=1,
        )
        self.assertEqual(payload["checkStatus"], "未对账")
        self.assertNotEqual(payload.get("checkStatus"), "已对账")
        self.assertNotIn("blockedAction", payload)


class OfficialPackageGuardTests(unittest.TestCase):
    def test_manifest_is_1_1_1_upload(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.1.1")
        self.assertEqual(manifest["rpaFlowId"], "rpa_flow_srm_stmt_upload_invoice")
        self.assertIn("srm_stmt_upload_invoice", manifest["supportedWorkflowCodes"])

    def test_selectors_have_no_data_rpa(self):
        raw = (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)

    def test_flow_scans_and_does_not_click_submit(self):
        raw = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertNotIn("data-rpa", raw)
        self.assertIn("#/reconciliation/reconciliationStatement", raw)
        self.assertIn("scan_invoices", raw)
        self.assertIn("el-table__fixed-body-wrapper", raw)
        self.assertIn("matchedDate", raw)
        self.assertNotIn("await adapter.click_submit", raw)
        self.assertNotIn("is_dry_run", raw)


if __name__ == "__main__":
    unittest.main()
