"""按 PO+料号查询采购凭证，回写行项目等到 Client。本 Run 不点 SRM 保存。"""

from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    login_boe_srm,
    open_invoice_packing,
)

OUTPUT_SCHEMA = "SRM_BOE_PACK_ENRICH_OUTPUT_V1"


def packing_lines_from_input(payload: Mapping) -> list[dict]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = summary.get("lines") if isinstance(summary.get("lines"), list) else []
    return [line for line in lines if isinstance(line, dict)]


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


def parse_popup_fields(blob: str) -> dict[str, str]:
    text = " ".join(str(blob or "").split())
    return {
        "itemName": text[:80],
        "remainingQty": "",
        "lineItem": "",
    }


async def run(ctx):
    payload = ctx.input if isinstance(ctx.input, Mapping) else {}
    lines = packing_lines_from_input(payload)
    sel = lambda name: _selector(ctx, name)
    page = ctx.page
    await login_boe_srm(ctx, selector=sel)
    await open_invoice_packing(ctx, selector=sel)
    await page.locator(sel("create_button")).first.click()
    await page.wait_for_timeout(800)
    enriched = []
    for line in lines:
        po_num = str(line.get("poNum") or "").strip()
        item_num = str(line.get("itemNum") or "").strip()
        await page.locator(sel("add_line_button")).first.click()
        await page.wait_for_timeout(400)
        await page.locator(sel("po_input")).first.fill(po_num)
        await page.locator(sel("item_input")).first.fill(item_num)
        await page.locator(sel("search_button")).first.click()
        await page.wait_for_timeout(800)
        rows = page.locator(sel("popup_row"))
        count = await _row_count(rows)
        if count != 1:
            raise RpaBusinessError(
                "BOE_PO_ITEM_NOT_UNIQUE",
                f"PO {po_num} 料号 {item_num} 搜索到 {count} 行",
            )
        await page.locator(sel("popup_checkbox")).first.click()
        parsed = parse_popup_fields(str(await rows.first.inner_text()))
        await page.locator(sel("popup_save")).first.click()
        await page.wait_for_timeout(500)
        enriched.append(
            {
                "poNum": po_num,
                "itemNum": item_num,
                "lineItem": line.get("lineItem") or parsed["lineItem"],
                "remainingQty": line.get("remainingQty") or parsed["remainingQty"],
                "itemName": line.get("itemName") or parsed["itemName"],
                "factory": line.get("factory") or "",
            }
        )
    return {
        "schemaVersion": OUTPUT_SCHEMA,
        "instanceId": payload.get("instanceId"),
        "docNo": payload.get("docNo"),
        "lines": enriched,
    }
