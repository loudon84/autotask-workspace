"""按 PO+料号查询采购凭证，回写行项目等到 Client。本 Run 不点 SRM 保存。

步骤对齐影刀实操与《发票箱单样例表单.md》（2026-09-07 探针实测）：
列表页点「新建」进单据页 → 关「启用AI识别」（否则表单锁定、新增禁用）→
选 BOE 工厂（否则点新增只 toast「请先填写基本信息中的工厂字段」）→
项目信息卡「新增」唤起采购凭证查询弹窗 → 填 PO+料号搜索 → 勾选 → 保存回填
→ 读项目信息表回填行取行项目/剩余开票数等。
"""

import re
from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    login_boe_srm,
    open_invoice_packing,
    prepare_invoice_create,
)

OUTPUT_SCHEMA = "SRM_BOE_PACK_ENRICH_OUTPUT_V1"


def packing_lines_from_input(payload: Mapping) -> list[dict]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = summary.get("lines") if isinstance(summary.get("lines"), list) else []
    return [line for line in lines if isinstance(line, dict)]


def packing_header_from_input(payload: Mapping) -> dict:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    header = summary.get("header") if isinstance(summary.get("header"), dict) else {}
    return header


def _selector(ctx, name: str) -> str:
    selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}
    value = selectors.get(name)
    if not value:
        raise RpaBusinessError("BOE_SELECTOR_MISSING", f"缺少选择器 {name}")
    return str(value)


async def _row_count(locator) -> int:
    try:
        return int(await locator.count())
    except Exception:
        return 0


def parse_item_row(blob: str, po_num: str) -> dict[str, str]:
    """解析项目信息表回填行 innerText（制表符分隔）。

    列序：序号/采购订单号/行项目/包装物/工厂/物料编码/物料描述/订单数量/
    订单单位/剩余开票数/本次开票数/…。以 PO 单元格定位，兼容前置复选框列。
    """
    cells = [c.strip() for c in re.split(r"[\t\n]", str(blob or ""))]
    try:
        i = cells.index(po_num)
    except ValueError:
        return {"lineItem": "", "factory": "", "itemName": "", "remainingQty": ""}

    def at(offset: int) -> str:
        idx = i + offset
        return cells[idx] if 0 <= idx < len(cells) else ""

    return {
        "lineItem": at(1),
        "factory": at(3),
        "itemName": at(5),
        "remainingQty": at(8),
    }


async def run(ctx):
    payload = ctx.input if isinstance(ctx.input, Mapping) else {}
    lines = packing_lines_from_input(payload)
    header = packing_header_from_input(payload)
    sel = lambda name: _selector(ctx, name)
    await login_boe_srm(ctx, selector=sel)
    page = await open_invoice_packing(ctx, selector=sel)
    await page.locator(sel("create_button")).first.click()
    await page.locator(sel("add_line_button")).first.wait_for(timeout=15000)
    # 关 AI 识别解锁表单 + 选 BOE 工厂（不选则无法新增项目信息行）
    await prepare_invoice_create(
        page, selector=sel, factory=str(header.get("factory") or "")
    )
    enriched = []
    for line in lines:
        po_num = str(line.get("poNum") or "").strip()
        item_num = str(line.get("itemNum") or "").strip()
        await page.locator(sel("add_line_button")).first.click()
        await page.locator(sel("popup")).first.wait_for(timeout=10000)
        await page.locator(sel("po_input")).first.fill(po_num)
        await page.locator(sel("item_input")).first.fill(item_num)
        await page.locator(sel("search_button")).first.click()
        await page.wait_for_timeout(1200)
        rows = page.locator(sel("popup_row"))
        count = await _row_count(rows)
        if count != 1:
            raise RpaBusinessError(
                "BOE_PO_ITEM_NOT_UNIQUE",
                f"PO {po_num} 料号 {item_num} 搜索到 {count} 行",
            )
        await page.locator(sel("popup_checkbox")).first.click()
        await page.locator(sel("popup_save")).first.click()
        popup = page.locator(sel("popup")).first
        try:
            await popup.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        await page.wait_for_timeout(800)
        # 读项目信息表回填行（含剩余开票数），取含该 PO 的最后一行
        item_rows = page.locator(sel("item_table_row"))
        row_count = await _row_count(item_rows)
        parsed = {"lineItem": "", "factory": "", "itemName": "", "remainingQty": ""}
        for idx in range(row_count - 1, -1, -1):
            blob = str(await item_rows.nth(idx).inner_text())
            if po_num in blob:
                parsed = parse_item_row(blob, po_num)
                break
        enriched.append(
            {
                "poNum": po_num,
                "itemNum": item_num,
                "lineItem": line.get("lineItem") or parsed["lineItem"],
                "remainingQty": line.get("remainingQty") or parsed["remainingQty"],
                "itemName": line.get("itemName") or parsed["itemName"],
                "factory": line.get("factory") or parsed["factory"],
            }
        )
    return {
        "schemaVersion": OUTPUT_SCHEMA,
        "instanceId": payload.get("instanceId"),
        "docNo": payload.get("docNo"),
        "lines": enriched,
    }
