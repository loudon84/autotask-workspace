import importlib.util
import sys
from pathlib import Path

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("boe_pack_submit_flow", FLOW_DIR / "flow.py")
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)


def test_header_and_line_diffs() -> None:
    changed = flow_module.header_diff(
        {"invoiceNo": "A", "factory": "1200"},
        {"invoiceNo": "B", "factory": "1200"},
    )
    assert list(changed) == ["invoiceNo"]
    diffs = flow_module.line_diffs(
        [{"poNum": "P1", "itemNum": "M1", "deliveryQty": "10"}],
        [{"poNum": "P1", "itemNum": "M1", "deliveryQty": "12"}],
    )
    assert diffs[0]["action"] == "update"
    packing = flow_module.packing_from_input(
        {
            "summary": {
                "srmDraftNo": "D9",
                "header": {"invoiceNo": "B"},
                "lines": [{"poNum": "P1", "itemNum": "M1", "deliveryQty": "12"}],
                "reviewBaseline": {
                    "header": {"invoiceNo": "A"},
                    "lines": [{"poNum": "P1", "itemNum": "M1", "deliveryQty": "10"}],
                },
            }
        }
    )
    assert packing["srmDraftNo"] == "D9"
    assert "invoiceNo" in packing["headerDiff"]
