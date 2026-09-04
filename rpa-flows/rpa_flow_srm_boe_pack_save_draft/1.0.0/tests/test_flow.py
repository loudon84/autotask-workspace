import importlib.util
import sys
from pathlib import Path

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("boe_pack_save_draft_flow", FLOW_DIR / "flow.py")
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)


def test_parse_draft_no_and_snapshot() -> None:
    assert flow_module.parse_draft_no("发票箱单流水号：FPX-001") == "FPX-001"
    packing = flow_module.packing_from_input(
        {
            "docNo": "DOC1",
            "summary": {
                "srmDraftNo": "D1",
                "header": {"invoiceNo": "INV", "factory": "1200"},
                "lines": [{"poNum": "P1"}],
            },
        }
    )
    assert packing["invoiceNo"] == "INV"
    assert packing["srmDraftNo"] == "D1"
    snap = flow_module.snapshot_from_packing(packing)
    assert snap["header"]["invoiceNo"] == "INV"
    assert snap["lines"] == [{"poNum": "P1"}]
