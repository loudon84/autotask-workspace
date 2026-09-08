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
    qty_unit = flow_module.line_diffs(
        [{"poNum": "P1", "itemNum": "M1", "orderQty": "10", "orderUnit": "EA"}],
        [{"poNum": "P1", "itemNum": "M1", "orderQty": "12", "orderUnit": "EA"}],
    )
    assert qty_unit[0]["fields"]["orderQty"] == ("10", "12")
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


class _Ctx:
    def __init__(self, config=None, payload=None):
        self.config = config
        self.input = payload


def test_attachments_from_summary_skips_empty_and_maps_bl() -> None:
    rows = flow_module.attachments_from_summary(
        {
            "attachments": [
                {"type": "箱单", "filePath": "D:/a/PL-1.pdf", "fileName": "PL-1.pdf"},
                {"type": "提单", "filePath": "D:/a/bl.pdf", "fileName": "bl.pdf"},
                {"type": "发票", "fileName": "x.pdf"},
            ]
        }
    )
    assert [item["type"] for item in rows] == ["箱单", "提运单"]
    assert rows[0]["filePath"].endswith("PL-1.pdf")


def test_submit_dry_run_defaults_closed() -> None:
    assert flow_module.boe_pack_submit_is_dry_run(_Ctx()) is True
    assert flow_module.boe_pack_submit_is_dry_run(_Ctx(config={"dryRun": True})) is True
    assert flow_module.boe_pack_submit_is_dry_run(_Ctx(config={"dryRun": False})) is False
    assert flow_module.boe_pack_submit_is_dry_run(_Ctx(payload={"dryRun": "false"})) is False
