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


def compact_number(value: str) -> str:
    """WMS 净重常带多余尾零（3.52100000000000000），填表前收成短小数。"""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    rendered = f"{number:.5f}".rstrip("0").rstrip(".")
    return rendered or "0"


def is_dual_sign_attach_type(value: str) -> bool:
    """新建页默认第 4 行文件类型是「双签PO/协议」；一期不传该附件，有空行会挡保存。"""
    return "双签" in str(value or "")


async def _fill(page, selector: str, value: str) -> None:
    loc = page.locator(selector)
    if await _count(loc) == 0:
        return
    await loc.first.fill(str(value or ""))


async def _fill_input_number(page, selector: str, value: str, *, last: bool = False) -> None:
    """el-input-number（总体积/开票数/净重）带静态 aria-disabled，Playwright fill 误判禁用拒填；
    实测 force 点击 + 键盘输入可正常填入且 Vue 接受（与用户手动一致），JS 赋值兜底。"""
    text = str(value or "")
    if not text:
        return
    loc = page.locator(selector)
    if await _count(loc) == 0:
        return
    el = loc.last if last else loc.first
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


async def _dismiss_dialog(page, sel) -> str:
    """关掉警告/确认框，返回框内文案（空则无框）。"""
    box = page.locator(".el-message-box:visible")
    if await _count(box) == 0:
        return ""
    text = ""
    try:
        text = str(await box.first.inner_text()).strip()
    except Exception:
        text = ""
    confirm = page.locator(sel("dialog_confirm"))
    if await _count(confirm):
        try:
            await confirm.first.click()
        except Exception:
            pass
    return text


async def _open_existing_or_create(page, sel, packing: dict) -> bool:
    """搜到唯一草稿则打开返回 False；否则点「新建」返回 True。"""
    key = packing["srmDraftNo"] or packing["invoiceNo"]
    if key:
        await _fill(page, sel("list_search"), key)
        await page.locator(sel("list_search_button")).first.click()
        await page.wait_for_timeout(800)
        rows = page.locator(sel("list_row"))
        if await _count(rows) == 1:
            # 流水号在首列，整行 click 不会进详情
            cell = rows.first.locator("td").first
            await cell.click()
            await page.wait_for_timeout(1200)
            return False
    await page.locator(sel("create_button")).first.click()
    await page.wait_for_timeout(800)
    return True


async def _last_visible(locator):
    found = None
    for idx in range(await _count(locator)):
        el = locator.nth(idx)
        try:
            if await el.is_visible():
                found = el
        except Exception:
            continue
    return found


async def _scroll_table_cell(locator) -> None:
    """项目信息表横向很宽，原产国/地区默认在可视区外（探针 rect.x≈2000）。"""
    await locator.evaluate(
        """e => {
            const td = e.closest('td');
            const wrap = e.closest('.el-table__body-wrapper');
            if (td && wrap) {
                const t = td.getBoundingClientRect();
                const w = wrap.getBoundingClientRect();
                wrap.scrollLeft += (t.left - w.left) - 80;
            }
            e.scrollIntoView({block: 'center', inline: 'nearest'});
        }"""
    )


async def _pick_region(page, sel, region: str) -> None:
    """原产国/地区是 filterable el-select：先滚进视口，点外壳打开，输入名称，再点选项才生效。

    只点选项或只输入都不稳。input 默认 readonly，要点 `.el-select` 不是 input。
    """
    region_loc = page.locator(sel("line_region"))
    el = await _last_visible(region_loc)
    if el is None:
        raise RpaBusinessError("BOE_REGION_INPUT_MISSING", "项目信息行未找到原产国/地区下拉")
    await _scroll_table_cell(el)
    await page.wait_for_timeout(300)
    select = el.locator("xpath=ancestor::div[contains(@class,'el-select')][1]")
    await select.click()
    await page.wait_for_timeout(400)
    await page.keyboard.type(region, delay=40)
    await page.wait_for_timeout(600)
    option = page.locator(sel("region_option")).get_by_text(region, exact=True)
    try:
        await option.first.click(timeout=8000)
    except Exception as exc:
        raise RpaBusinessError(
            "BOE_REGION_OPTION_MISSING",
            f"原产国/地区下拉没有「{region}」",
        ) from exc
    await page.wait_for_timeout(300)
    try:
        value = str(await el.input_value() or "").strip()
    except Exception:
        value = ""
    if value != region:
        raise RpaBusinessError(
            "BOE_REGION_NOT_SET",
            f"原产国/地区选择后仍为「{value}」，期望「{region}」",
        )


async def _fill_last_line(page, sel, line: dict) -> None:
    """挂行回填后，填最后一行的本次开票数 / 净重 / 原产国地区（影刀同序）。"""
    qty = compact_number(str(line.get("deliveryQty") or ""))
    net = compact_number(str(line.get("netWeight") or ""))
    region = str(line.get("regionSrmName") or "").strip()
    qty_loc = page.locator(sel("line_qty"))
    if qty and await _count(qty_loc):
        await _fill_input_number(page, sel("line_qty"), qty, last=True)
    net_loc = page.locator(sel("line_net_weight"))
    if net and await _count(net_loc):
        await _fill_input_number(page, sel("line_net_weight"), net, last=True)
    if not region:
        raise RpaBusinessError(
            "BOE_REGION_UNMAPPED",
            f"行 {line.get('poNum')} 无 SRM 地区名，请先在基础数据维护原产地映射",
        )
    await _pick_region(page, sel, region)


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
    warn = await _dismiss_dialog(page, sel)
    if "不允许创建" in warn or "已经存在草稿" in warn:
        raise RpaBusinessError("BOE_PO_DRAFT_EXISTS", warn[:200])
    await _fill_last_line(page, sel, line)


async def _delete_dual_sign_attach(page, sel) -> int:
    """删掉附件表里文件类型为「双签PO/协议」的行（一期不传，空行会挡保存）。"""
    deleted = 0
    for _ in range(8):
        rows = page.locator(sel("attach_row"))
        count = await _count(rows)
        target = None
        for idx in range(count):
            row = rows.nth(idx)
            type_input = row.locator(sel("attach_type")).first
            if await _count(type_input) == 0:
                continue
            try:
                value = str(await type_input.input_value() or "")
            except Exception:
                value = ""
            if is_dual_sign_attach_type(value):
                target = row
                break
        if target is None:
            break
        button = target.locator(sel("attach_delete")).first
        await button.click()
        await page.wait_for_timeout(400)
        await _dismiss_dialog(page, sel)
        deleted += 1
        await page.wait_for_timeout(400)
    return deleted


async def _read_draft_no(page, sel, packing: dict) -> str:
    if packing["srmDraftNo"]:
        return packing["srmDraftNo"]
    page_text = ""
    try:
        page_text = str(await page.content())
    except Exception:
        page_text = ""
    parsed = parse_draft_no(page_text)
    if parsed:
        return parsed
    loc = page.locator(sel("draft_no"))
    if await _count(loc) == 0:
        return ""
    try:
        value = str(await loc.first.input_value() or "").strip()
    except Exception:
        value = ""
    if value:
        return value
    try:
        return str(await loc.first.inner_text()).strip()
    except Exception:
        return ""


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
        await _delete_dual_sign_attach(page, sel)
        await page.locator(sel("save_button")).first.click()
        await page.wait_for_timeout(1500)
        warn = await _dismiss_dialog(page, sel)
        if warn and "成功" not in warn:
            raise RpaBusinessError("BOE_SAVE_DRAFT_REJECTED", warn[:200])
        draft_no = await _read_draft_no(page, sel, packing)
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

