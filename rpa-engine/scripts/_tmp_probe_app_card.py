"""临时探针 v5：复现「点交货计划管理不开新页签」。

A 组（模拟 Flow 当前时序）：登录成功标志一出现立刻点应用卡。
B 组（修复后时序）：可见后等 1.5s 再点，失败重试。

用法：uv run python scripts/_tmp_probe_app_card.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

SESSION = Path(
    r"d:\work_space260811\autotask-workspace\rpa-engine\runtime-cache\sessions"
    r"\a3668cbaf0893c4e9651e1b67765b8fc19518dfd9c068a83453b51e3adac67f4\storage_state.json"
)
HOME = "https://supply.boe.com"
CARD = "div.quickText:has-text('交货计划管理')"
MENU = ".ant-menu span.menu-span:has-text('首页')"


async def to_dashboard(context) -> "object":
    page = await context.new_page()
    await page.goto(HOME, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    entry = page.locator("div.buttonSign:has-text('供应商登录')")
    if await entry.count() and await entry.first.is_visible():
        await entry.first.click()
    await page.locator(MENU).first.wait_for(state="visible", timeout=20000)
    return page


async def try_click(page, label: str, settle_ms: int) -> bool:
    """点应用卡，返回是否打开了 bsrm 页。"""
    card = page.locator(CARD).first
    await card.wait_for(state="visible", timeout=15000)
    if settle_ms:
        await page.wait_for_timeout(settle_ms)
    pages_before = len(page.context.pages)
    try:
        async with page.context.expect_page(timeout=8000) as new_info:
            await card.click()
        new_page = await new_info.value
        print(f"  [{label}] 新页签: {new_page.url[:80]}")
        return True
    except Exception:
        await page.wait_for_timeout(1500)
        if "bsrm.boe.com" in page.url:
            print(f"  [{label}] 同页跳: {page.url[:80]}")
            return True
        if len(page.context.pages) > pages_before:
            print(f"  [{label}] 新页签(迟到): {page.context.pages[-1].url[:80]}")
            return True
        print(f"  [{label}] 点击无效（没开页）")
        return False


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        print("== A 组：菜单一出现立刻点（模拟当前 Flow） ==")
        ctx = await browser.new_context(storage_state=str(SESSION))
        page = await to_dashboard(ctx)
        ok = await try_click(page, "A 立即点", settle_ms=0)
        if not ok:
            ok = await try_click(page, "A 重试", settle_ms=0)
        await ctx.close()

        print("== B 组：可见后等 1.5s 再点 ==")
        ctx = await browser.new_context(storage_state=str(SESSION))
        page = await to_dashboard(ctx)
        ok = await try_click(page, "B 等1.5s", settle_ms=1500)
        if not ok:
            ok = await try_click(page, "B 重试", settle_ms=1500)
        await ctx.close()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
