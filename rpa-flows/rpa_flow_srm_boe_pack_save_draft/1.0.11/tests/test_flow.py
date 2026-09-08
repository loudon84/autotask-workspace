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


def test_compact_number_and_dual_sign_type() -> None:
    assert flow_module.compact_number("3.52100000000000000") == "3.521"
    assert flow_module.compact_number("5000") == "5000"
    assert flow_module.compact_number("") == ""
    assert flow_module.is_dual_sign_attach_type("双签PO/协议") is True
    assert flow_module.is_dual_sign_attach_type("箱单") is False
    assert flow_module.is_dual_sign_attach_type("发票") is False


def test_packing_keeps_multiple_lines_in_order() -> None:
    packing = flow_module.packing_from_input(
        {
            "docNo": "DOC1",
            "summary": {
                "header": {"invoiceNo": "INV"},
                "lines": [
                    {"poNum": "P1", "itemNum": "M1", "regionSrmName": "中国台湾"},
                    {"poNum": "P2", "itemNum": "M2", "regionSrmName": "中国香港"},
                ],
            },
        }
    )
    assert [line["poNum"] for line in packing["lines"]] == ["P1", "P2"]
    assert packing["lines"][1]["regionSrmName"] == "中国香港"


def test_draft_no_from_list_row_requires_invoice_and_draft() -> None:
    blob = "I260907250\n草稿\n101SJH202609195\n1200"
    assert flow_module.draft_no_from_list_row(blob, "101SJH202609195") == "I260907250"
    assert flow_module.draft_no_from_list_row(blob, "OTHER") == ""
    assert flow_module.draft_no_from_list_row("I260907250\n待采购确认\n101SJH202609195", "101SJH202609195") == ""
