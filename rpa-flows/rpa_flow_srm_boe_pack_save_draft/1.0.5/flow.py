"""按 Client 当前单据重建发票箱单并保存 SRM 草稿。一期不传附件。"""

import re
from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    login_boe_srm,
    open_invoice_packing,
    prepare_invoice_create,
)

OUTPUT_SCHEMA = "SRM_BOE_PACK_SAVE_DRAFT_OUTPUT_V1"
DRAFT_NO_RE = re.compile(r"(?:发票箱单流水号|流水号)[:：\s]*([A-Za-z0-9\-]+)")
HEADER_SELECTOR = {
    "invoiceNo": "invoice_no",
    "invoiceDate": "invoice_date",
    "etd": "etd",
    "consignArrivalDate": "consign_date",
    # 总体积是 el-input-number，带静态 aria-disabled 属性，Playwright fill 会误判
    # 禁用而空等超时；实际可输入（force 点击+键盘），单独走 _fill_input_number。
}


def packing_from_input(payload: Mapping) -> dict:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    header = summary.get("header") if isinstance(summary.get("header"), dict) else {}
    lines = [line for line in (summary.get("lines") or []) if isinstance(line, dict)]
    return {
        "header": header,
        "lines": lines,
        "srmDraftNo": str(summary.get("srmDraftNo") or "").strip(),
        "invoiceNo": str(header.get("invoiceNo") or payload.get("docNo") or "").strip(),
    }


def snapshot_from_packing(packing: dict) -> dict:
    return {
        "header": {
            key: packing["header"].get(key, "")
            for key in ("invoiceNo", "factory", "invoiceDate", "etd", "consignArrivalDate", "totalVol")
        },
        "lines": packing["lines"],
    }


def parse_draft_no(text: str) -> str:
    match = DRAFT_NO_RE.search(str(text or ""))
    return match.group(1) if match else ""


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


async def _fill_input_number(page, selector: str, value: str) -> None:
    """el-input-number（总体积）带静态 aria-disabled，Playwright fill 误判禁用拒填；
    实测 force 点击 + 键盘输入可正常填入且 Vue 接受（与用户手动一致），JS 赋值兜底。"""
    text = str(value or "")
    if not text:
        return
    loc = page.locator(selector)
    if await _count(loc) == 0:
        return
    el = loc.first
    try:
        await el.click(force=True, timeout=5000)
        await el.press("Control+a")
        await page.keyboard.type(text, delay=30)
        await el.press("Tab")
        return
    except Exception:
        pass
    await el.evaluate(
        "(el, v) => { const s = Object.getOwnPropertyDescriptor("
        "window.HTMLInputElement.prototype, 'value').set; s.call(el, v);"
        " el.dispatchEvent(new Event('input', {bubbles: true}));"
        " el.dispatchEvent(new Event('change', {bubbles: true})); }",
        text,
    )


async def _open_existing_or_create(page, sel, packing: dict) -> bool:
    """搜到唯一草稿则打开返回 False；否则点「新建」返回 True。"""
    key = packing["srmDraftNo"] or packing["invoiceNo"]
    if key:
        await _fill(page, sel("list_search"), key)
        await page.locator(sel("list_search_button")).first.click()
        await page.wait_for_timeout(800)
        rows = page.locator(sel("list_row"))
        if await _count(rows) == 1:
            await rows.first.click()
            await page.wait_for_timeout(800)
            return False
    await page.locator(sel("create_button")).first.click()
    await page.wait_for_timeout(800)
    return True


async def _attach_line(page, sel, line: dict) -> None:
    po_num = str(line.get("poNum") or "").strip()
    item_num = str(line.get("itemNum") or "").strip()
    await page.locator(sel("add_line_button")).first.click()
    await page.locator(sel("popup")).first.wait_for(timeout=10000)
    await _fill(page, sel("po_input"), po_num)
    await _fill(page, sel("item_input"), item_num)
    await page.locator(sel("popup_search_button")).first.click()
    await page.wait_for_timeout(1200)
    rows = page.locator(sel("popup_row"))
    count = await _count(rows)
    if count != 1:
        raise RpaBusinessError(
            "BOE_PO_ITEM_NOT_UNIQUE",
            f"PO {po_num} 料号 {item_num} 搜索到 {count} 行",
        )
    await page.locator(sel("popup_checkbox")).first.click()
    await page.locator(sel("popup_save")).first.click()
    try:
        await page.locator(sel("popup")).first.wait_for(state="hidden", timeout=10000)
    except Exception:
        pass
    await page.wait_for_timeout(800)


async def run(ctx):
    payload = ctx.input if isinstance(ctx.input, Mapping) else {}
    packing = packing_from_input(payload)
    sel = lambda name: _selector(ctx, name)
    await login_boe_srm(ctx, selector=sel)
    page = await open_invoice_packing(ctx, selector=sel)
    try:
        created = await _open_existing_or_create(page, sel, packing)
        header = packing["header"]
        if created:
            # 新建页默认「启用AI识别=是」锁全表单；且必须先选工厂才能新增行
            await prepare_invoice_create(
                page, selector=sel, factory=str(header.get("factory") or "")
            )
        else:
            try:
                await page.locator(sel("ai_recognize_no")).first.click()
            except Exception:
                pass
        for field, selector_name in HEADER_SELECTOR.items():
            await _fill(page, sel(selector_name), str(header.get(field) or ""))
        # 总体积：el-input-number，fill 会被 aria-disabled 挡住，用键盘输入
        await _fill_input_number(page, sel("total_vol"), str(header.get("totalVol") or ""))
        for line in packing["lines"]:
            await _attach_line(page, sel, line)
        await page.locator(sel("save_button")).first.click()
        await page.wait_for_timeout(1200)
        page_text = ""
        try:
            page_text = str(await page.content())
        except Exception:
            page_text = ""
        draft_no = packing["srmDraftNo"] or parse_draft_no(page_text)
        if not draft_no:
            try:
                draft_no = str(await page.locator(sel("draft_no")).first.inner_text()).strip()
            except Exception:
                draft_no = ""
        if not draft_no:
            raise RpaBusinessError("BOE_DRAFT_NO_MISSING", "保存后未读到发票箱单流水号")
        return {
            "schemaVersion": OUTPUT_SCHEMA,
            "instanceId": payload.get("instanceId"),
            "docNo": payload.get("docNo"),
            "srmDraftNo": draft_no,
        }
    except Exception as exc:
        _ = snapshot_from_packing(packing)
        if isinstance(exc, RpaBusinessError):
            raise
        raise RpaBusinessError("BOE_SAVE_DRAFT_FAILED", str(exc)[:200]) from exc
