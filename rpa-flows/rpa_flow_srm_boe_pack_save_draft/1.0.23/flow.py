"""按 Client 当前单据重建发票箱单并保存 SRM 草稿。一期不传附件。"""

import re
import time
from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    login_boe_srm,
    open_invoice_packing,
    prepare_invoice_create,
)

OUTPUT_SCHEMA = "SRM_BOE_PACK_SAVE_DRAFT_OUTPUT_V1"
DRAFT_NO_RE = re.compile(r"(?:发票箱单流水号|流水号)[:：\s]*([A-Za-z0-9\-]+)")
LIST_DRAFT_NO_RE = re.compile(r"\b(I\d{6,})\b")
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


def draft_no_from_list_row(blob: str, invoice_no: str) -> str:
    """列表行必须同时含供应商发票号和「草稿」，流水号形如 I260907250。"""
    text = str(blob or "")
    invoice = str(invoice_no or "").strip()
    if invoice and invoice not in text:
        return ""
    if "草稿" not in text:
        return ""
    match = LIST_DRAFT_NO_RE.search(text)
    return match.group(1) if match else ""


def is_pack_save_url(url: str) -> bool:
    """保存草稿会 POST create/update；接口可能很慢甚至不回包，但库里已经有单。"""
    text = str(url or "")
    if "/invoicepackinglist/" not in text:
        return False
    return any(token in text for token in ("/create", "/update", "/modify", "/save"))


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


async def _wait_popup_data(page, rows, *needles: str, timeout_ms: int = 15000) -> int:
    """采购凭证点搜索后，等「有数据」再找行（影刀：搜索有数据）。"""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        matched = 0
        for idx in range(await _count(rows)):
            blob = " ".join(str(await rows.nth(idx).inner_text() or "").split())
            if not blob or "暂无数据" in blob:
                continue
            if all(needle in blob for needle in needles if needle):
                matched += 1
        if matched:
            return matched
        await page.wait_for_timeout(400)
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
    loc = page.locator(selector)
    if await _count(loc) == 0:
        return
    el = loc.last if last else loc.first
    await _type_number(page, el, value)


async def _type_number(page, el, value: str) -> None:
    text = str(value or "")
    if not text:
        return
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


async def _pick_list_status_draft(page, sel) -> None:
    """状态是只读多选 el-select；已带「草稿」标签时不再点，避免第二次搜索反选。"""
    wrap = page.locator(".invoice-list .el-select:has(input[placeholder='状态'])")
    if await _count(wrap) == 0:
        return
    try:
        already = str(await wrap.first.inner_text() or "")
    except Exception:
        already = ""
    if "草稿" in already:
        return
    try:
        await wrap.first.click()
        await page.wait_for_timeout(300)
        draft_opt = page.locator(sel("list_status_draft"))
        if await _count(draft_opt):
            await draft_opt.first.click()
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(200)
    except Exception:
        pass


async def _search_list_by_invoice(page, sel, invoice_no: str) -> None:
    """影刀查询草稿：展开 → 填供应商发票号 → 状态选草稿 → 搜 索。"""
    # @lat: [[flow-packages#BOE packing Flows]]
    expand = page.locator(sel("list_expand"))
    if await _count(expand):
        try:
            if await expand.first.is_visible():
                await expand.first.click()
                await page.wait_for_timeout(600)
        except Exception:
            pass
    invoice = page.locator(sel("list_search"))
    try:
        await invoice.first.wait_for(state="visible", timeout=8000)
    except Exception as exc:
        raise RpaBusinessError(
            "BOE_LIST_INVOICE_INPUT_MISSING",
            "列表未找到供应商发票号搜索框（需先展开搜索条件）",
        ) from exc
    await invoice.first.fill(invoice_no)
    await _pick_list_status_draft(page, sel)
    await page.locator(sel("list_search_button")).first.click()
    await page.wait_for_timeout(1500)


async def _first_visible(locator):
    for idx in range(await _count(locator)):
        el = locator.nth(idx)
        try:
            if await el.is_visible():
                return el
        except Exception:
            continue
    return None


async def _list_draft_button(page, sel):
    """影刀：流水号是可见的文本按钮 I…；主表首列 rowspan 勾选格被冻结列盖住，点不到。"""
    return await _first_visible(page.locator(sel("list_draft_no")))


async def _draft_no_from_button(button) -> str:
    if button is None:
        return ""
    try:
        text = str(await button.inner_text()).strip()
    except Exception:
        return ""
    return text if LIST_DRAFT_NO_RE.fullmatch(text) else ""


async def _open_list_draft(page, sel, button) -> None:
    target = button or await _list_draft_button(page, sel)
    if target is None:
        raise RpaBusinessError("BOE_DRAFT_OPEN_FAILED", "列表找到草稿但流水号按钮不可点")
    await target.click(timeout=8000)
    await page.wait_for_timeout(1200)


async def _open_existing_or_create(page, sel, packing: dict) -> tuple[bool, str]:
    """搜到唯一草稿则 (False, 流水号)；否则点「新建」返回 (True, '')。

    Client 还没有 srmDraftNo 时只回写列表流水号，不强行打开（上次保存已成功）。
    已有流水号再跑则点影刀的 I… 按钮进详情更新。
    """
    if packing["invoiceNo"]:
        await _search_list_by_invoice(page, sel, packing["invoiceNo"])
        rows = page.locator(sel("list_row"))
        if await _count(rows) == 1:
            button = await _list_draft_button(page, sel)
            draft_no = await _draft_no_from_button(button)
            if draft_no and not packing["srmDraftNo"]:
                return False, draft_no
            await _open_list_draft(page, sel, button)
            return False, draft_no
    elif packing["srmDraftNo"]:
        await _fill(page, sel("list_search"), packing["srmDraftNo"])
        await page.locator(sel("list_search_button")).first.click()
        await page.wait_for_timeout(800)
        rows = page.locator(sel("list_row"))
        if await _count(rows) == 1:
            await _open_list_draft(page, sel, None)
            return False, packing["srmDraftNo"]
    await page.locator(sel("create_button")).first.click()
    await page.wait_for_timeout(800)
    return True, ""


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


async def _pick_region(page, sel, region: str, region_input) -> None:
    """原产国/地区是 filterable el-select：先滚进视口，点外壳打开，输入名称，再点选项才生效。

    只点选项或只输入都不稳。input 默认 readonly，要点 `.el-select` 不是 input。
    调用方传入「当前行」的 input，避免多行时点到上一行或冻结列克隆。
    """
    await _scroll_table_cell(region_input)
    await page.wait_for_timeout(300)
    select = region_input.locator("xpath=ancestor::div[contains(@class,'el-select')][1]")
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
        value = str(await region_input.input_value() or "").strip()
    except Exception:
        value = ""
    if value != region:
        raise RpaBusinessError(
            "BOE_REGION_NOT_SET",
            f"原产国/地区选择后仍为「{value}」，期望「{region}」",
        )
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass


async def _fill_attached_line(page, sel, line: dict) -> None:
    """只填刚挂上的那一行（主表 last row），多行时不复用全表 .last input。"""
    rows = page.locator(sel("item_data_row"))
    count = await _count(rows)
    if count < 1:
        raise RpaBusinessError("BOE_ITEM_ROW_MISSING", "挂行后项目信息表没有数据行")
    row = rows.nth(count - 1)
    await row.scroll_into_view_if_needed()
    await page.wait_for_timeout(200)
    qty = compact_number(str(line.get("deliveryQty") or ""))
    net = compact_number(str(line.get("netWeight") or ""))
    region = str(line.get("regionSrmName") or "").strip()
    qty_el = await _last_visible(row.locator(sel("line_qty")))
    if qty and qty_el is not None:
        await _type_number(page, qty_el, qty)
    net_el = await _last_visible(row.locator(sel("line_net_weight")))
    if net and net_el is not None:
        await _type_number(page, net_el, net)
    if not region:
        raise RpaBusinessError(
            "BOE_REGION_UNMAPPED",
            f"行 {line.get('poNum')} 无 SRM 地区名，请先在基础数据维护原产地映射",
        )
    region_el = await _last_visible(row.locator(sel("line_region")))
    if region_el is None:
        raise RpaBusinessError("BOE_REGION_INPUT_MISSING", "当前行未找到原产国/地区下拉")
    await _pick_region(page, sel, region, region_el)


async def _attach_line(page, sel, line: dict) -> None:
    po_num = str(line.get("poNum") or "").strip()
    item_num = str(line.get("itemNum") or "").strip()
    await page.locator(sel("add_line_button")).first.click()
    await page.locator(sel("popup")).first.wait_for(timeout=10000)
    await _fill(page, sel("po_input"), po_num)
    await _fill(page, sel("item_input"), item_num)
    await page.locator(sel("popup_search_button")).first.click()
    rows = page.locator(sel("popup_row"))
    count = await _wait_popup_data(page, rows, po_num, item_num)
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
    await _fill_attached_line(page, sel, line)


async def _delete_dual_sign_attach(page, sel) -> int:
    """删掉附件表里文件类型为「双签PO/协议」的行（一期不传，空行会挡保存）。

    操作列在 el-table__fixed-right：主表行里的删除按钮 visible=false（被冻结列盖住），
    Playwright click 会空等 30s。箱单/发票/提运单的删除是 disabled，只有双签能删。
    """
    deleted = 0
    card = page.locator(".el-card.item-card:has-text('附件信息')").first
    try:
        await card.scroll_into_view_if_needed()
    except Exception:
        pass
    await page.wait_for_timeout(300)
    for _ in range(20):
        rows = page.locator(sel("attach_row"))
        idx = None
        for i in range(await _count(rows)):
            type_input = rows.nth(i).locator(sel("attach_type")).first
            if await _count(type_input) == 0:
                continue
            try:
                value = str(await type_input.input_value() or "")
            except Exception:
                value = ""
            if is_dual_sign_attach_type(value):
                idx = i
                break
        if idx is None:
            break
        fixed = page.locator(sel("attach_fixed_row"))
        if await _count(fixed) <= idx:
            raise RpaBusinessError("BOE_ATTACH_DELETE_MISSING", "附件冻结列找不到对应删除按钮")
        button = fixed.nth(idx).locator(sel("attach_delete")).first
        await button.click(timeout=8000)
        await page.wait_for_timeout(400)
        await _dismiss_dialog(page, sel)
        deleted += 1
        await page.wait_for_timeout(400)
    return deleted


def _live_page(page):
    """保存后当前窗口可能关、也可能一直停在表单（create 不回包）。"""
    try:
        pages = [p for p in page.context.pages if not p.is_closed()]
        if pages:
            return pages[-1]
    except Exception:
        pass
    return page


async def _read_draft_no_from_form(page, sel) -> str:
    loc = page.locator(sel("draft_no"))
    if await _count(loc) == 0:
        return ""
    try:
        value = str(await loc.first.input_value() or "").strip()
    except Exception:
        value = ""
    match = LIST_DRAFT_NO_RE.search(value)
    if match:
        return match.group(1)
    try:
        text = str(await loc.first.inner_text() or "").strip()
    except Exception:
        text = ""
    match = LIST_DRAFT_NO_RE.search(text)
    return match.group(1) if match else ""


async def _click_back_to_list(page, sel) -> None:
    back = page.locator(sel("back_button"))
    if await _count(back) == 0:
        return
    try:
        await back.first.click(timeout=4000)
        await page.wait_for_timeout(800)
    except Exception:
        pass


async def _read_list_row_text(page, sel, idx: int) -> str:
    parts = []
    fixed = page.locator(sel("list_fixed_row"))
    if await _count(fixed) > idx:
        try:
            parts.append(str(await fixed.nth(idx).inner_text()))
        except Exception:
            pass
    rows = page.locator(sel("list_row"))
    if await _count(rows) > idx:
        try:
            parts.append(str(await rows.nth(idx).inner_text()))
        except Exception:
            pass
    return "\n".join(parts)


async def _read_draft_no_from_list(page, sel, invoice_no: str) -> str:
    """保存关窗后回列表：按供应商发票号搜索，取第一条匹配的草稿流水号。"""
    invoice_no = str(invoice_no or "").strip()
    if not invoice_no:
        raise RpaBusinessError("BOE_INVOICE_NO_MISSING", "保存后回列表需要供应商发票号")
    page = _live_page(page)
    listed = False
    for _ in range(12):
        page = _live_page(page)
        if await _count(page.locator(".invoice-list")):
            listed = True
            break
        await page.wait_for_timeout(500)
    if not listed:
        raise RpaBusinessError("BOE_LIST_NOT_FOUND", "保存后未回到发票箱单列表")
    await page.wait_for_timeout(800)
    last_blob = ""
    for _ in range(4):
        page = _live_page(page)
        await _search_list_by_invoice(page, sel, invoice_no)
        rows = page.locator(sel("list_row"))
        if await _count(rows) < 1:
            await page.wait_for_timeout(2000)
            continue
        link = page.locator(sel("list_draft_no"))
        if await _count(link):
            try:
                text = str(await link.first.inner_text()).strip()
            except Exception:
                text = ""
            if LIST_DRAFT_NO_RE.fullmatch(text):
                blob = await _read_list_row_text(page, sel, 0)
                if not invoice_no or invoice_no in blob or not blob:
                    return text
        last_blob = await _read_list_row_text(page, sel, 0)
        draft_no = draft_no_from_list_row(last_blob, invoice_no)
        if draft_no:
            return draft_no
        await page.wait_for_timeout(2000)
    if last_blob:
        raise RpaBusinessError(
            "BOE_DRAFT_NO_MISSING",
            f"列表首行不是发票号 {invoice_no} 的草稿：{last_blob[:120]}",
        )
    raise RpaBusinessError(
        "BOE_DRAFT_NO_MISSING",
        f"列表未找到供应商发票号 {invoice_no} 的草稿",
    )


async def _read_draft_no_after_save(page, sel, invoice_no: str) -> str:
    """create 可能不关窗、甚至不回 HTTP。先看表单流水号，没有就点返回再搜列表。"""
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        page = _live_page(page)
        if await _count(page.locator(".invoice-list")):
            return await _read_draft_no_from_list(page, sel, invoice_no)
        form_no = await _read_draft_no_from_form(page, sel)
        if form_no:
            return form_no
        await _dismiss_dialog(page, sel)
        await page.wait_for_timeout(500)
    page = _live_page(page)
    form_no = await _read_draft_no_from_form(page, sel)
    if form_no:
        return form_no
    await _click_back_to_list(page, sel)
    page = _live_page(page)
    return await _read_draft_no_from_list(page, sel, invoice_no)


async def run(ctx):
    payload = ctx.input if isinstance(ctx.input, Mapping) else {}
    packing = packing_from_input(payload)
    sel = lambda name: _selector(ctx, name)
    await login_boe_srm(ctx, selector=sel)
    page = await open_invoice_packing(ctx, selector=sel)
    try:
        created, existing_no = await _open_existing_or_create(page, sel, packing)
        if existing_no and not created and not packing["srmDraftNo"]:
            return {
                "schemaVersion": OUTPUT_SCHEMA,
                "instanceId": payload.get("instanceId"),
                "docNo": payload.get("docNo"),
                "srmDraftNo": existing_no,
            }
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
            try:
                await _attach_line(page, sel, line)
            except RpaBusinessError as exc:
                # 上次保存已成功但没读到流水号时，重跑会打开已有草稿；同 PO 再挂行会报已存在。
                if not created and exc.code == "BOE_PO_DRAFT_EXISTS":
                    continue
                raise
        await _delete_dual_sign_attach(page, sel)
        try:
            async with page.expect_response(
                lambda response: is_pack_save_url(response.url),
                timeout=25000,
            ) as pending:
                await page.locator(sel("save_button")).first.click()
            await pending.value
        except Exception:
            pass
        await page.wait_for_timeout(800)
        page = _live_page(page)
        warn = await _dismiss_dialog(page, sel)
        if warn and "成功" not in warn:
            raise RpaBusinessError("BOE_SAVE_DRAFT_REJECTED", warn[:200])
        draft_no = await _read_draft_no_after_save(page, sel, packing["invoiceNo"])
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

