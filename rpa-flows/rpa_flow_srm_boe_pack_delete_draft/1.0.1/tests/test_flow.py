import importlib.util
import json
import sys
from pathlib import Path

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("boe_pack_delete_draft_flow", FLOW_DIR / "flow.py")
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)


def test_selectors_follow_yingdao_delete_and_frozen_checkbox() -> None:
    selectors = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))
    assert selectors["list_search"] == ".invoice-list input[placeholder='发票箱单流水号']"
    assert "avue-crud__search" in selectors["list_search_button"]
    assert "el-table__fixed" in selectors["list_checkbox"]
    assert "el-button--danger" in selectors["list_delete"]
    assert "aria-label='删除'" in selectors["delete_confirm"]


def test_draft_no_from_summary() -> None:
    assert flow_module.draft_no_from_input({"summary": {"srmDraftNo": "I260910001"}}) == "I260910001"
    assert flow_module.draft_no_from_input({"srmDraftNo": "I2"}) == "I2"
    assert flow_module.draft_no_from_input({}) == ""


def test_list_already_gone() -> None:
    assert flow_module.list_already_gone("暂无数据", "I260910001") is True
    assert flow_module.list_already_gone("发票箱单流水号 I260910001 草稿", "I260910001") is False
    assert flow_module.list_already_gone("其它单 I999", "I260910001") is True


def test_after_delete_empty_ignores_search_box_draft_no() -> None:
    blob = "发票箱单流水号 I260910102 搜 索 暂无数据"
    assert flow_module.list_shows_empty(blob) is True
    assert flow_module.list_already_gone(blob, "I260910102") is True
    assert flow_module.list_shows_empty("发票箱单流水号 I260910102 草稿") is False
