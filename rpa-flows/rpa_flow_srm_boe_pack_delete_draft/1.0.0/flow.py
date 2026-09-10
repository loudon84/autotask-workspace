"""按流水号查 SRM 草稿：还在就勾选删除（影刀「删除-草稿单删除」），没有则视为已删。"""

from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    login_boe_srm,
    open_invoice_packing,
)

OUTPUT_SCHEMA = "SRM_BOE_PACK_DELETE_DRAFT_OUTPUT_V1"


def _text(value) -> str:
    return str(value or "").strip()


def draft_no_from_input(payload: Mapping) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return _text(payload.get("srmDraftNo") or summary.get("srmDraftNo"))


def list_already_gone(blob: str, draft_no: str) -> bool:
    """列表「暂无数据」、或不含该流水号，都算 SRM 侧已经没有这张草稿。"""
    text = " ".join(str(blob or "").split())
    if "暂无数据" in text:
        return True
    return draft_no not in text


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


def _live_page(page):
    try:
        pages = [item for item in page.context.pages if not item.is_closed()]
        if pages:
            return pages[-1]
    except Exception:
        pass
    return page


async def _expand_list_search(page, sel) -> None:
    expand = page.locator(sel("list_expand"))
    if await _count(expand) == 0:
        return
    try:
        if await expand.first.is_visible():
            await expand.first.click()
            await page.wait_for_timeout(600)
    except Exception:
        pass


async def _search_draft(page, sel, draft_no: str):
    await _expand_list_search(page, sel)
    field = page.locator(sel("list_search"))
    try:
        await field.first.wait_for(state="visible", timeout=8000)
    except Exception as exc:
        raise RpaBusinessError(
            "BOE_LIST_DRAFT_INPUT_MISSING",
            "列表未找到发票箱单流水号搜索框（需先展开搜索条件）",
        ) from exc
    await field.first.fill(draft_no)
    await page.locator(sel("list_search_button")).first.click()
    await page.wait_for_timeout(1200)
    return _live_page(page)


async def _list_blob(page) -> str:
    loc = page.locator(".invoice-list")
    if await _count(loc) == 0:
        return ""
    try:
        return await loc.first.inner_text()
    except Exception:
        return ""


async def _delete_visible_draft(page, sel, draft_no: str) -> None:
    """影刀：冻结列勾选（主表勾选格被盖住）→ 菜单「删除」→ 确认框「确定」。"""
    boxes = page.locator(sel("list_checkbox"))
    if await _count(boxes) == 0:
        raise RpaBusinessError("BOE_DRAFT_CHECKBOX_MISSING", f"列表有流水号 {draft_no} 但勾不到冻结列复选框")
    await boxes.first.click(force=True)
    await page.wait_for_timeout(400)
    delete_btn = page.locator(sel("list_delete"))
    if await _count(delete_btn) == 0:
        raise RpaBusinessError("BOE_DRAFT_DELETE_MISSING", "找不到影刀「删除-草稿单删除」按钮")
    await delete_btn.first.click()
    confirm = page.locator(sel("delete_confirm"))
    try:
        await confirm.first.wait_for(state="visible", timeout=8000)
    except Exception as exc:
        raise RpaBusinessError("BOE_DRAFT_DELETE_CONFIRM_MISSING", "未出现删除确认框") from exc
    await confirm.first.click()
    await page.wait_for_timeout(1200)


async def run(ctx):
    payload = ctx.input if isinstance(ctx.input, Mapping) else {}
    draft_no = draft_no_from_input(payload)
    if not draft_no:
        raise RpaFatalError("BOE_DRAFT_NO_REQUIRED", "删除 SRM 草稿需要发票箱单流水号")

    sel = lambda name: _selector(ctx, name)
    await login_boe_srm(ctx, selector=sel)
    page = await open_invoice_packing(ctx, selector=sel)
    page = await _search_draft(page, sel, draft_no)
    blob = await _list_blob(page)
    if list_already_gone(blob, draft_no):
        return {
            "schemaVersion": OUTPUT_SCHEMA,
            "srmDraftNo": draft_no,
            "deleted": False,
            "alreadyMissing": True,
        }

    await _delete_visible_draft(page, sel, draft_no)
    page = await _search_draft(_live_page(page), sel, draft_no)
    blob = await _list_blob(page)
    if not list_already_gone(blob, draft_no):
        raise RpaBusinessError("BOE_DRAFT_STILL_PRESENT", f"删除后列表仍有流水号 {draft_no}")
    return {
        "schemaVersion": OUTPUT_SCHEMA,
        "srmDraftNo": draft_no,
        "deleted": True,
        "alreadyMissing": False,
    }
