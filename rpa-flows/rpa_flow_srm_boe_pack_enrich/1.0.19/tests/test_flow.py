import importlib.util
import sys
from pathlib import Path

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("boe_pack_enrich_flow", FLOW_DIR / "flow.py")
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)


def test_output_schema_constant() -> None:
    assert flow_module.OUTPUT_SCHEMA.endswith("ENRICH_OUTPUT_V1")


def test_packing_lines_from_input() -> None:
    lines = flow_module.packing_lines_from_input(
        {"summary": {"lines": [{"poNum": "P1", "itemNum": "M1"}, "skip"]}}
    )
    assert lines == [{"poNum": "P1", "itemNum": "M1"}]


def test_parse_item_row_by_po_anchor() -> None:
    # 项目信息表回填行：序号/PO/行项目/包装物/工厂/物料编码/物料描述/订单数量/订单单位/剩余开票数/…
    blob = "1\t9100048919\t0010\t否\t1200\t47-7001645\tTCON_MT9520-128P\t7500\tEA\t4920\t4500"
    parsed = flow_module.parse_item_row(blob, "9100048919")
    assert parsed == {
        "lineItem": "0010",
        "factory": "1200",
        "itemName": "TCON_MT9520-128P",
        "orderQty": "7500",
        "orderUnit": "EA",
        "remainingQty": "4920",
        "netWeightUnit": "",
    }


def test_parse_item_row_with_leading_checkbox_cell() -> None:
    blob = "\t2\t9100056294\t0010\t否\t1200\t47-7001645\tTCON_MT9520-128P\t3500\tEA\t3500\t2700"
    parsed = flow_module.parse_item_row(blob, "9100056294")
    assert parsed["lineItem"] == "0010"
    assert parsed["remainingQty"] == "3500"


def test_parse_item_row_po_missing() -> None:
    parsed = flow_module.parse_item_row("1\t9100048919\t0010", "0000000000")
    assert parsed["lineItem"] == ""
    assert parsed["orderQty"] == ""


def test_parse_item_cells_split_fixed_and_main() -> None:
    # 真实 DOM（2026-09-07 探针）：序号~物料编码在 .el-table__fixed 冻结克隆，
    # 物料描述起在主表；两段 td 非空文本拼接后按 PO 锚点解析
    fixed = ["1", "9100069442", "00010", "否", "1200", "47-7001373"]
    main = ["TCON_ MST7554TP1_88P", "20700", "EA", "20700", "0", "0", "337", "USD"]
    parsed = flow_module.parse_item_cells(fixed + main, "9100069442")
    assert parsed == {
        "lineItem": "00010",
        "factory": "1200",
        "itemName": "TCON_ MST7554TP1_88P",
        "orderQty": "20700",
        "orderUnit": "EA",
        "remainingQty": "20700",
        "netWeightUnit": "",
    }
    with_unit = flow_module.parse_item_cells(
        fixed + ["TCON_ MST7554TP1_88P", "20700", "EA", "20700", "10", "1.2", "KG"],
        "9100069442",
    )
    assert with_unit["netWeightUnit"] == "KG"
