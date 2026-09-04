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
