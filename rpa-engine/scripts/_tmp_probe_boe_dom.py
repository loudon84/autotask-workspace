"""临时探针 v2：带 BOE 会话走完整 enrich 路径，逐级验证选择器。

路径：首页 → 供应商登录(SSO) → dashboard → 交货计划管理应用卡 → bsrm
→ 送货管理 → 发票箱单 → 新建 → 项目信息「新增」→ 采购凭证查询弹窗（搜索一个真实 PO，不点保存）。

用法：uv run python scripts/_tmp_probe_boe_dom.py
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
PROBE_PO = "9100048919"  # 样例表单里的真实 PO，只搜索不保存

SEL = {
    "entry": "div.buttonSign:has-text('供应商登录')",
    "ant_menu_home": ".ant-menu span.menu-span:has-text('首页')",
    "app_card": "div.quickText:has-text('交货计划管理')",
    "nav_delivery": "div.el-submenu__title:has-text('送货管理')",
    "nav_invoice_packing": "li.el-menu-item:has-text('发票箱单')",
    "create_button": ".invoice-list .avue-crud__menu button:has-text('新建')",
    "add_line_button": ".el-card.item-card:has-text('项目信息') .avue-crud__menu .avue-crud__left button:has-text('新增')",
    "popup": ".el-dialog[aria-label='采购凭证查询']",
    "po_input": ".el-dialog[aria-label='采购凭证查询'] input[placeholder*='采购订单号']",
    "item_input": ".el-dialog[aria-label='采购凭证查询'] input[placeholder*='物料编码']",
    "search_button": ".el-dialog[aria-label='采购凭证查询'] button:has-text('搜索'), .el-dialog[aria-label='采购凭证查询'] button:has-text('搜 索')",
    "popup_row": ".el-dialog[aria-label='采购凭证查询'] .el-table > .el-table__body-wrapper tbody tr",
    "popup_checkbox": ".el-dialog[aria-label='采购凭证查询'] .el-table__fixed-header-wrapper th.el-table-column--selection .el-checkbox__inner",
    "popup_save": ".el-dialog[aria-label='采购凭证查询'] .avue-crud__menu button:has-text('保存')",
    "item_table_row": ".el-card.item-card:has-text('项目信息') .el-table > .el-table__body-wrapper tbody tr",
}


async def check(page, name: str) -> bool:
    loc = page.locator(SEL[name])
    try:
        count = await loc.count()
        visible = await loc.first.is_visible() if count else False
    except Exception as exc:
        print(f"  [ERR ] {name}: {exc}")
        return False
    mark = "OK  " if count and visible else "MISS"
    print(f"  [{mark}] {name}: count={count} visible={visible}")
    return bool(count and visible)


async def click(page, name: str) -> None:
    await page.locator(SEL[name]).first.click()
    print(f"  >> click {name}")


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(SESSION))
        page = await context.new_page()

        print("== 1. 首页 ==")
        await page.goto(HOME, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        print(" url:", page.url)
        await check(page, "entry")

        print("== 2. 点供应商登录（SSO） ==")
        await click(page, "entry")
        await page.wait_for_timeout(6000)
        print(" url:", page.url)
        await check(page, "ant_menu_home")
        await check(page, "app_card")

        print("== 3. 点交货计划管理应用卡 ==")
        pages_before = len(context.pages)
        async with context.expect_page(timeout=10000) as new_info:
            await click(page, "app_card")
        try:
            page = await new_info.value
            print(" 新开标签页:", page.url)
        except Exception:
            print(" 同页跳转:", page.url)
        await page.wait_for_timeout(5000)
        print(" tabs:", len(context.pages), "active url:", page.url)
        await check(page, "nav_delivery")

        print("== 4. 送货管理 → 发票箱单 ==")
        await click(page, "nav_delivery")
        await page.wait_for_timeout(1500)
        await check(page, "nav_invoice_packing")
        await click(page, "nav_invoice_packing")
        await page.wait_for_timeout(4000)
        print(" url:", page.url)
        await check(page, "create_button")

        print("== 5. 新建 → 项目信息新增 ==")
        await click(page, "create_button")
        await page.wait_for_timeout(5000)
        print(" url:", page.url)
        await check(page, "add_line_button")
        await click(page, "add_line_button")
        await page.wait_for_timeout(3000)
        if not await check(page, "popup"):
            # 弹窗 aria-label 可能不同，兜底找所有 dialog
            dialogs = await page.evaluate(
                """() => [...document.querySelectorAll('.el-dialog')]
                    .map(d => ({aria: d.getAttribute('aria-label'), visible: !!d.offsetParent}))"""
            )
            print("  页面上的 el-dialog:", dialogs)
        else:
            await check(page, "po_input")
            await check(page, "item_input")
            await check(page, "search_button")
            print(f"== 6. 弹窗内搜索 PO {PROBE_PO}（不点保存） ==")
            await page.locator(SEL["po_input"]).first.fill(PROBE_PO)
            await page.locator(SEL["search_button"]).first.click()
            await page.wait_for_timeout(4000)
            await check(page, "popup_row")
            rows = page.locator(SEL["popup_row"])
            count = await rows.count()
            print(f"  结果行数: {count}")
            if count:
                print("  首行文本:", (await rows.first.inner_text())[:200].replace("\n", " | "))
            await check(page, "popup_checkbox")
            await check(page, "popup_save")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
