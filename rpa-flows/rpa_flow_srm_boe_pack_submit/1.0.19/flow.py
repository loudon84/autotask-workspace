"""打开已有 SRM 草稿：可真传附件并保存；dryRun 只保存不点提交。"""

import time
from collections.abc import Mapping
from pathlib import Path

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
LINE_KEYS = (
    "deliveryQty",
    "netWeight",
    "netWeightUnit",
    "regionCode",
    "regionSrmName",
    "lineItem",
    "orderQty",
    "orderUnit",
    "remainingQty",
)
WRITABLE_LINE_FIELDS = ("deliveryQty", "netWeight")
NUMERIC_KEYS = {
    "deliveryQty",
    "netWeight",
    "orderQty",
    "remainingQty",
    "totalVol",
}


def _text(value) -> str:
    return str(value or "").strip()


def compact_number(value) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    rendered = f"{number:.5f}".rstrip("0").rstrip(".")
    return rendered or "0"


def _field_text(key: str, value) -> str:
    text = _text(value)
    if key in NUMERIC_KEYS:
        return compact_number(text)
    return text


def is_data_blob(blob: str, *needles: str) -> bool:
    """空表 / 「暂无数据」不算；影刀「搜索有数据」后再找元素。"""
    text = " ".join(str(blob or "").split())
    if not text or "暂无数据" in text:
        return False
    return all(needle in text for needle in needles if needle)


def boe_pack_submit_is_dry_run(ctx) -> bool:
    """缺省或 Binding dryRun=true 一律演练；只有显式 false 才允许真点提交。"""
    for source in (getattr(ctx, "config", None), getattr(ctx, "input", None)):
        if not isinstance(source, Mapping):
            continue
        if "dryRun" not in source and "dry_run" not in source:
            continue
        raw = source.get("dryRun", source.get("dry_run"))
        if raw is False or str(raw).strip().lower() in {"false", "0", "no"}:
            return False
        return True
    return True


def line_key(line: Mapping) -> str:
    return f"{_text(line.get('poNum'))}|{_text(line.get('itemNum'))}"


def header_diff(baseline: Mapping, current: Mapping) -> dict[str, tuple[str, str]]:
    changed = {}
    for key in HEADER_KEYS:
        before = _field_text(key, baseline.get(key))
        after = _field_text(key, current.get(key))
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
            field: (_field_text(field, previous.get(field)), _field_text(field, line.get(field)))
            for field in LINE_KEYS
            if _field_text(field, previous.get(field)) != _field_text(field, line.get(field))
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
        "attachments": attachments_from_summary(summary),
    }


def attachments_from_summary(summary: Mapping) -> list[dict]:
    """客服核验页选的本地 PDF：type + 绝对路径，提交 Run 真传到 SRM。"""
    rows = []
    for item in summary.get("attachments") or []:
        if not isinstance(item, dict):
            continue
        kind = _text(item.get("type") or item.get("fileType"))
        if kind == "提单":
            kind = "提运单"
        path = _text(item.get("filePath") or item.get("path"))
        name = _text(item.get("fileName") or item.get("name"))
        if not kind or not path:
            continue
        rows.append({"type": kind, "filePath": path, "fileName": name})
    return rows


def require_attachment_files(rows: list[dict]) -> list[dict]:
    ready = []
    for row in rows:
        path = Path(row["filePath"])
        if not path.is_file():
            raise RpaFatalError(
                "BOE_ATTACH_FILE_MISSING",
                f"附件文件不存在：{row.get('fileName') or path.name}",
            )
        ready.append({**row, "filePath": str(path)})
    return ready


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


def _live_page(page):
    try:
        pages = [item for item in page.context.pages if not item.is_closed()]
        if pages:
            return pages[-1]
    except Exception:
        pass
    return page


async def _dismiss_dialog(page, sel) -> None:
    confirm = page.locator(sel("dialog_confirm"))
    if await _count(confirm) == 0:
        return
    try:
        await confirm.first.click()
    except Exception:
        pass


async def _open_draft(page, sel, draft_no: str):
    await _fill(page, sel("list_search"), draft_no)
    await page.locator(sel("list_search_button")).first.click()
    row, count = await _wait_matching_row(page, page.locator(sel("list_row")), draft_no)
    if row is None or count != 1:
        raise RpaBusinessError("BOE_DRAFT_NOT_FOUND", f"列表未唯一找到流水号 {draft_no}")
    link = page.locator(
        ".invoice-list button.el-button--text, "
        ".invoice-list .el-table__fixed tbody tr button.el-button--text"
    )
    for idx in range(await _count(link)):
        el = link.nth(idx)
        try:
            if await el.is_visible():
                await el.click(timeout=8000)
                await page.wait_for_timeout(800)
                return _live_page(page)
        except Exception:
            continue
    raise RpaBusinessError("BOE_DRAFT_OPEN_FAILED", f"找不到可点的流水号 {draft_no}")


async def _row_type(row, sel) -> str:
    field = row.locator(sel("attach_type"))
    if await _count(field) == 0:
        return ""
    try:
        return _text(await field.first.input_value())
    except Exception:
        return ""


async def _pick_attach_type(page, sel, row, kind: str) -> None:
    field = row.locator(sel("attach_type"))
    if await _count(field) == 0:
        raise RpaBusinessError("BOE_ATTACH_TYPE_MISSING", f"附件行没有类型下拉：{kind}")
    wrap = field.first.locator("xpath=ancestor::div[contains(@class,'el-select')][1]")
    await wrap.click()
    await page.wait_for_timeout(300)
    option = page.locator(sel("attach_type_option")).get_by_text(kind, exact=True)
    if await _count(option) == 0:
        raise RpaBusinessError("BOE_ATTACH_TYPE_OPTION", f"附件类型没有「{kind}」")
    await option.first.click()
    await page.wait_for_timeout(200)
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass


async def _upload_into_row(page, sel, idx: int, file_path: str) -> None:
    fixed = page.locator(sel("attach_fixed_row"))
    row = page.locator(sel("attach_row"))
    target = fixed.nth(idx) if await _count(fixed) > idx else row.nth(idx)
    file_input = target.locator(sel("attach_file"))
    if await _count(file_input) == 0:
        file_input = row.nth(idx).locator(sel("attach_file"))
    if await _count(file_input) == 0:
        raise RpaBusinessError("BOE_ATTACH_INPUT_MISSING", "附件行没有文件选择框")
    await file_input.first.set_input_files(file_path)
    await page.wait_for_timeout(800)
    await _dismiss_dialog(page, sel)


async def _ensure_attach_row(page, sel, kind: str, used: set[int]) -> int:
    rows = page.locator(sel("attach_row"))
    for idx in range(await _count(rows)):
        if idx in used:
            continue
        if await _row_type(rows.nth(idx), sel) == kind:
            return idx
    await page.locator(sel("attach_add")).first.click()
    await page.wait_for_timeout(400)
    idx = await _count(page.locator(sel("attach_row"))) - 1
    if idx < 0:
        raise RpaBusinessError("BOE_ATTACH_ROW_MISSING", "新增附件行失败")
    await _pick_attach_type(page, sel, page.locator(sel("attach_row")).nth(idx), kind)
    return idx


async def _upload_attachments(page, sel, attachments: list[dict]) -> int:
    if not attachments:
        return 0
    try:
        await page.locator(".el-card.item-card:has-text('附件信息')").first.scroll_into_view_if_needed()
    except Exception:
        pass
    await page.wait_for_timeout(300)
    used: set[int] = set()
    uploaded = 0
    for item in attachments:
        idx = await _ensure_attach_row(page, sel, item["type"], used)
        used.add(idx)
        await _upload_into_row(page, sel, idx, item["filePath"])
        uploaded += 1
    return uploaded


async def _row_blob(row) -> str:
    parts: list[str] = []
    try:
        parts.append(str(await row.inner_text() or ""))
    except Exception:
        pass
    try:
        inputs = row.locator("input")
        for idx in range(await _count(inputs)):
            try:
                parts.append(str(await inputs.nth(idx).input_value() or ""))
            except Exception:
                continue
    except Exception:
        pass
    return " ".join(parts)


async def _wait_matching_row(page, rows, *needles: str, timeout_ms: int = 15000):
    """先搜，等表格真有数据再返回行。空 tr / 暂无数据不算。"""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        found = None
        matched = 0
        for idx in range(await _count(rows)):
            blob = await _row_blob(rows.nth(idx))
            if not is_data_blob(blob, *needles):
                continue
            matched += 1
            if found is None:
                found = rows.nth(idx)
        if found is not None:
            return found, matched
        await page.wait_for_timeout(400)
    return None, 0


async def _find_item_row(page, sel, po_num: str, item_num: str):
    """PO/料号在左侧冻结列，本次开票数/净重在主表；两段拼起来定位，返回主表行。"""
    main_rows = page.locator(sel("item_data_row"))
    fixed_rows = page.locator(sel("item_fixed_row"))
    main_count = await _count(main_rows)
    fixed_count = await _count(fixed_rows)
    for idx in range(main_count):
        main = main_rows.nth(idx)
        fixed = fixed_rows.nth(idx) if idx < fixed_count else None
        blob = (await _row_blob(fixed) if fixed is not None else "") + " " + await _row_blob(main)
        if is_data_blob(blob, po_num, item_num):
            return main
    return None


async def _wait_item_row(page, sel, po_num: str, item_num: str, timeout_ms: int = 15000):
    """打开草稿后项目信息可能还空着：有数据才去找开票数/净重。"""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        row = await _find_item_row(page, sel, po_num, item_num)
        if row is not None:
            return row
        await page.wait_for_timeout(400)
    return None


async def _apply_line_field_updates(page, sel, line: dict, fields: dict) -> None:
    row = await _wait_item_row(
        page, sel, _text(line.get("poNum")), _text(line.get("itemNum"))
    )
    if row is None:
        raise RpaBusinessError(
            "BOE_LINE_ROW_MISSING",
            f"草稿里找不到行 {_text(line.get('poNum'))}|{_text(line.get('itemNum'))}",
        )
    await row.scroll_into_view_if_needed()
    mapping = (("deliveryQty", "line_qty"), ("netWeight", "line_net_weight"))
    for field, name in mapping:
        if field not in fields:
            continue
        loc = row.locator(sel(name))
        if await _count(loc) == 0:
            continue
        await loc.first.click(force=True, timeout=5000)
        await loc.first.press("Control+a")
        await page.keyboard.type(str(fields[field][1] or ""), delay=30)
        await loc.first.press("Tab")


async def _apply_diffs(page, sel, packing: dict) -> None:
    for key, (_before, after) in packing["headerDiff"].items():
        selector_name = HEADER_SELECTOR.get(key)
        if not selector_name:
            continue
        if key == "totalVol":
            await _fill_input_number(page, sel(selector_name), after)
        else:
            await _fill(page, sel(selector_name), after)
    for item in packing["lineDiffs"]:
        if item["action"] == "update":
            writable = {
                key: value
                for key, value in (item.get("fields") or {}).items()
                if key in WRITABLE_LINE_FIELDS
            }
            if writable:
                await _apply_line_field_updates(page, sel, item["line"], writable)
            continue
        if item["action"] != "add":
            continue
        line = item["line"]
        await page.locator(sel("add_line_button")).first.click()
        await page.locator(sel("popup")).first.wait_for(timeout=10000)
        await _fill(page, sel("po_input"), _text(line.get("poNum")))
        await _fill(page, sel("item_input"), _text(line.get("itemNum")))
        await page.locator(sel("popup_search_button")).first.click()
        _row, count = await _wait_matching_row(
            page,
            page.locator(sel("popup_row")),
            _text(line.get("poNum")),
            _text(line.get("itemNum")),
        )
        if count != 1:
            raise RpaBusinessError(
                "BOE_PO_ITEM_NOT_UNIQUE",
                f"PO {_text(line.get('poNum'))} 料号 {_text(line.get('itemNum'))} 搜索到 {count} 行",
            )
        await page.locator(sel("popup_checkbox")).first.click()
        await page.locator(sel("popup_save")).first.click()
        try:
            await page.locator(sel("popup")).first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        await page.wait_for_timeout(800)


async def _trial_or_click_submit(page, sel, *, dry_run: bool) -> None:
    submit = page.locator(sel("submit_button")).first
    try:
        await submit.wait_for(state="visible", timeout=15000)
    except Exception as exc:
        raise RpaBusinessError("BOE_SUBMIT_BUTTON_MISSING", "未找到 SRM 提交按钮") from exc
    if dry_run:
        try:
            await submit.click(trial=True, timeout=8000)
        except Exception as exc:
            raise RpaBusinessError(
                "BOE_SUBMIT_BUTTON_NOT_READY",
                "演练未通过提交按钮可点性检查（未真实点击）",
            ) from exc
        return
    await submit.click()
    await page.wait_for_timeout(1200)


async def run(ctx):
    payload = ctx.input if isinstance(ctx.input, Mapping) else {}
    dry_run = boe_pack_submit_is_dry_run(ctx)
    packing = packing_from_input(payload)
    draft_no = packing["srmDraftNo"]
    if not draft_no:
        raise RpaFatalError("BOE_DRAFT_NO_REQUIRED", "提交需要 SRM 草稿流水号")
    attachments = require_attachment_files(packing["attachments"])
    sel = lambda name: _selector(ctx, name)
    await login_boe_srm(ctx, selector=sel)
    page = await open_invoice_packing(ctx, selector=sel)
    page = await _open_draft(page, sel, draft_no)
    await _apply_diffs(page, sel, packing)
    uploaded = await _upload_attachments(page, sel, attachments)
    await page.locator(sel("save_button")).first.click()
    await page.wait_for_timeout(1500)
    page = _live_page(page)
    await _dismiss_dialog(page, sel)
    if dry_run:
        return {
            "schemaVersion": OUTPUT_SCHEMA,
            "instanceId": payload.get("instanceId"),
            "docNo": payload.get("docNo"),
            "srmDraftNo": draft_no,
            "committed": False,
            "dryRun": True,
            "blockedAction": "srm_submit",
            "uploadedAttachmentCount": uploaded,
            "appliedHeaderFields": list(packing["headerDiff"].keys()),
            "appliedLineChanges": len(packing["lineDiffs"]),
        }
    await _trial_or_click_submit(page, sel, dry_run=False)
    return {
        "schemaVersion": OUTPUT_SCHEMA,
        "instanceId": payload.get("instanceId"),
        "docNo": payload.get("docNo"),
        "srmDraftNo": draft_no,
        "committed": True,
        "dryRun": False,
        "uploadedAttachmentCount": uploaded,
        "appliedHeaderFields": list(packing["headerDiff"].keys()),
        "appliedLineChanges": len(packing["lineDiffs"]),
    }
