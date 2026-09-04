"""打开已有 SRM 草稿，只打 reviewBaseline 与当前 Client 的 diff 后提交。"""

from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    login_boe_srm,
    open_invoice_packing,
)

OUTPUT_SCHEMA = "SRM_BOE_PACK_SUBMIT_OUTPUT_V1"
HEADER_KEYS = (
    "invoiceNo",
    "factory",
    "invoiceDate",
    "etd",
    "consignArrivalDate",
    "totalVol",
)
HEADER_SELECTOR = {
    "invoiceNo": "invoice_no",
    "invoiceDate": "invoice_date",
    "etd": "etd",
    "consignArrivalDate": "consign_date",
    "totalVol": "total_vol",
    "factory": "factory",
}
LINE_KEYS = ("deliveryQty", "netWeight", "regionCode", "regionSrmName", "lineItem")


def _text(value) -> str:
    return str(value or "").strip()


def line_key(line: Mapping) -> str:
    return f"{_text(line.get('poNum'))}|{_text(line.get('itemNum'))}"


def header_diff(baseline: Mapping, current: Mapping) -> dict[str, tuple[str, str]]:
    changed = {}
    for key in HEADER_KEYS:
        before = _text(baseline.get(key))
        after = _text(current.get(key))
        if before != after:
            changed[key] = (before, after)
    return changed


def line_diffs(baseline_lines: list, current_lines: list) -> list[dict]:
    base_map = {
        line_key(line): line
        for line in baseline_lines
        if isinstance(line, Mapping)
    }
    diffs = []
    seen = set()
    for line in current_lines:
        if not isinstance(line, Mapping):
            continue
        key = line_key(line)
        seen.add(key)
        previous = base_map.get(key)
        if previous is None:
            diffs.append({"key": key, "action": "add", "line": dict(line)})
            continue
        fields = {
            field: (_text(previous.get(field)), _text(line.get(field)))
            for field in LINE_KEYS
            if _text(previous.get(field)) != _text(line.get(field))
        }
        if fields:
            diffs.append({"key": key, "action": "update", "fields": fields, "line": dict(line)})
    for line in baseline_lines:
        if not isinstance(line, Mapping):
            continue
        key = line_key(line)
        if key not in seen:
            diffs.append({"key": key, "action": "remove", "line": dict(line)})
    return diffs


def packing_from_input(payload: Mapping) -> dict:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    header = summary.get("header") if isinstance(summary.get("header"), dict) else {}
    lines = [line for line in (summary.get("lines") or []) if isinstance(line, dict)]
    baseline = summary.get("reviewBaseline") if isinstance(summary.get("reviewBaseline"), dict) else {}
    base_header = baseline.get("header") if isinstance(baseline.get("header"), dict) else {}
    base_lines = [line for line in (baseline.get("lines") or []) if isinstance(line, dict)]
    return {
        "header": header,
        "lines": lines,
        "srmDraftNo": str(summary.get("srmDraftNo") or baseline.get("srmDraftNo") or "").strip(),
        "headerDiff": header_diff(base_header, header),
        "lineDiffs": line_diffs(base_lines, lines),
    }


def _selector(ctx, name: str) -> str:
    selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}
    value = selectors.get(name)
    if not value:
        raise RpaBusinessError("BOE_SELECTOR_MISSING", f"缺少选择器 {name}")
    return str(value)


async def _count(locator) -> int:
    try:
        return int(await locator.count())
    except Exception:
        return 0


async def _fill(page, selector: str, value: str) -> None:
    loc = page.locator(selector)
    if await _count(loc) == 0:
        return
    await loc.first.fill(str(value or ""))


async def run(ctx):
    payload = ctx.input if isinstance(ctx.input, Mapping) else {}
    packing = packing_from_input(payload)
    draft_no = packing["srmDraftNo"]
    if not draft_no:
        raise RpaFatalError("BOE_DRAFT_NO_REQUIRED", "提交需要 SRM 草稿流水号")
    sel = lambda name: _selector(ctx, name)
    page = ctx.page
    await login_boe_srm(ctx, selector=sel)
    await open_invoice_packing(ctx, selector=sel)
    await _fill(page, sel("list_search"), draft_no)
    await page.locator(sel("search_button")).first.click()
    await page.wait_for_timeout(800)
    rows = page.locator(sel("list_row"))
    if await _count(rows) != 1:
        raise RpaBusinessError("BOE_DRAFT_NOT_FOUND", f"列表未唯一找到流水号 {draft_no}")
    await rows.first.click()
    await page.wait_for_timeout(800)
    for key, (_before, after) in packing["headerDiff"].items():
        selector_name = HEADER_SELECTOR.get(key)
        if selector_name:
            await _fill(page, sel(selector_name), after)
    for item in packing["lineDiffs"]:
        if item["action"] == "remove":
            continue
        if item["action"] == "add":
            line = item["line"]
            await page.locator(sel("add_line_button")).first.click()
            await page.wait_for_timeout(400)
            await _fill(page, sel("po_input"), _text(line.get("poNum")))
            await _fill(page, sel("item_input"), _text(line.get("itemNum")))
            await page.locator(sel("search_button")).first.click()
            await page.wait_for_timeout(800)
            if await _count(page.locator(sel("popup_row"))) == 1:
                await page.locator(sel("popup_checkbox")).first.click()
                await page.locator(sel("popup_save")).first.click()
    await page.locator(sel("submit_button")).first.click()
    await page.wait_for_timeout(1200)
    return {
        "schemaVersion": OUTPUT_SCHEMA,
        "instanceId": payload.get("instanceId"),
        "docNo": payload.get("docNo"),
        "srmDraftNo": draft_no,
        "appliedHeaderFields": list(packing["headerDiff"].keys()),
        "appliedLineChanges": len(packing["lineDiffs"]),
    }
