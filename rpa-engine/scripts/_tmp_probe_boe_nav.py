"""临时探针 v6：bsrm 侧栏菜单结构 + 点送货管理后的真实状态。

用法：uv run python scripts/_tmp_probe_boe_nav.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

SESSION = Path(
    r"d:\work_space260811\autotask-workspace\rpa-engine\runtime-cache\sessions"
    r"\a3668cbaf0893c4e9651e1b67765b8fc19518dfd9c068a83453b51e3adac67f4\storage_state.json"
)
HOME = "https://supply.boe.com"


async def dump_menu(page, label: str) -> None:
    print(f"\n--- {label} ---")
    data = await page.evaluate(
        """() => {
            const subs = [...document.querySelectorAll('.el-submenu')].map(s => {
                const title = s.querySelector('.el-submenu__title');
                const ul = s.querySelector('ul.el-menu');
                return {
                    title: title ? title.textContent.trim().slice(0, 12) : '',
                    titleVisible: !!(title && title.offsetParent),
                    expanded: ul ? (ul.style.display !== 'none' && !!ul.offsetParent) : false,
                    items: ul ? [...ul.querySelectorAll('li.el-menu-item')].map(li => ({
                        text: li.textContent.trim().slice(0, 10),
                        visible: !!li.offsetParent,
                    })) : [],
                };
            });
            const packing = [...document.querySelectorAll('li.el-menu-item')]
                .filter(li => li.textContent.includes('发票箱单'))
                .map(li => ({text: li.textContent.trim(), visible: !!li.offsetParent,
                             display: getComputedStyle(li).display,
                             parentUlDisplay: li.closest('ul') ? getComputedStyle(li.closest('ul')).display : ''}));
            return {submenus: subs, packingItems: packing};
        }"""
    )
    for s in data["submenus"]:
        print(f"  [{s['title']}] titleVisible={s['titleVisible']} expanded={s['expanded']} items={json.dumps(s['items'], ensure_ascii=False)}")
    print("  发票箱单 li:", json.dumps(data["packingItems"], ensure_ascii=False))


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(SESSION))
        page = await context.new_page()
        await page.goto(HOME, wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)
        await page.locator("div.buttonSign:has-text('供应商登录')").first.click()
        await page.locator(".ant-menu span.menu-span:has-text('首页')").first.wait_for(state="visible", timeout=20000)
        async with context.expect_page(timeout=10000) as new_info:
            await page.locator("div.quickText:has-text('交货计划管理')").first.click()
        page = await new_info.value
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3000)
        print("bsrm url:", page.url)

        await dump_menu(page, "刚进 DeliveryPlan")

        nav = page.locator("div.el-submenu__title:has-text('送货管理')")
        print("\nnav_delivery count:", await nav.count())
        await nav.first.click()
        await page.wait_for_timeout(1500)
        await dump_menu(page, "点送货管理后 1.5s")

        await page.screenshot(path="scripts/_tmp_nav.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
