"""临时探针 v4：为什么点「新增」弹窗不开？

1. dump 新增按钮的真实 HTML 与事件绑定线索
2. 点击后 5 秒内每秒截图 + dump toast(.el-message) + dialog 可见性
3. dump BOE工厂 form-item 的内部结构（怎么唤起获取工厂弹窗）

用法：uv run python scripts/_tmp_probe_boe_dialog.py
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
ADD_LINE = ".el-card.item-card:has-text('项目信息') .avue-crud__menu .avue-crud__left button:has-text('新增')"


async def walk_to_create(context, page):
    await page.goto(HOME, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    await page.locator("div.buttonSign:has-text('供应商登录')").first.click()
    await page.wait_for_timeout(6000)
    async with context.expect_page(timeout=10000) as new_info:
        await page.locator("div.quickText:has-text('交货计划管理')").first.click()
    page = await new_info.value
    await page.wait_for_timeout(5000)
    await page.locator("div.el-submenu__title:has-text('送货管理')").first.click()
    await page.wait_for_timeout(1500)
    await page.locator("li.el-menu-item:has-text('发票箱单')").first.click()
    await page.wait_for_timeout(4000)
    await page.locator(".invoice-list .avue-crud__menu button:has-text('新建')").first.click()
    await page.wait_for_timeout(5000)
    await page.locator(
        ".el-form-item:has-text('启用AI识别') .el-radio:has-text('否'), "
        ".el-form-item:has-text('启用AI识别') .el-radio-button:has-text('否')"
    ).first.click()
    await page.wait_for_timeout(2000)
    print("create page ready:", page.url)
    return page


async def dialog_state(page) -> str:
    return await page.evaluate(
        """() => {
            const d = [...document.querySelectorAll('.el-dialog')]
                .filter(x => x.offsetParent)
                .map(x => ({aria: x.getAttribute('aria-label'), inputs: x.querySelectorAll('input').length, tables: x.querySelectorAll('.el-table').length}));
            const toasts = [...document.querySelectorAll('.el-message')]
                .map(m => (m.textContent||'').trim()).filter(t => t);
            return JSON.stringify({dialogs: d, toasts}, null, 0);
        }"""
    )


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(SESSION))
        page = await walk_to_create(context, await context.new_page())

        print("\n== 新增按钮 HTML ==")
        btn_html = await page.evaluate(
            """() => {
                const cards = [...document.querySelectorAll('.el-card.item-card')];
                return cards.map((c, i) => {
                    const header = c.querySelector('.el-card__header');
                    const btns = [...c.querySelectorAll('button')].map(b => (b.textContent||'').trim());
                    return {i, header: header ? header.textContent.trim().slice(0,20) : '', btns};
                });
            }"""
        )
        print(json.dumps(btn_html, ensure_ascii=False, indent=1))

        print("\n== BOE工厂 form-item 结构 ==")
        factory_html = await page.evaluate(
            """() => {
                const f = [...document.querySelectorAll('.el-form-item')]
                    .find(x => (x.querySelector('label')||{}).textContent?.includes('BOE工厂') && !(x.querySelector('label')||{}).textContent?.includes('名称'));
                return f ? f.querySelector('.el-form-item__content')?.innerHTML?.slice(0, 500) : 'not found';
            }"""
        )
        print(factory_html)

        print("\n== 点工厂搜索按钮，唤起「获取工厂」 ==")
        search_btn = page.locator(".el-form-item:has-text('BOE工厂') button.content-search").first
        print("  content-search count:", await search_btn.count())
        await search_btn.click()
        await page.wait_for_timeout(3000)
        print("  ", await dialog_state(page))
        dlg = page.locator(".el-dialog[aria-label='获取工厂']")
        if await dlg.count():
            inputs = await page.evaluate(
                """() => {
                    const d = document.querySelector(".el-dialog[aria-label='获取工厂']");
                    return [...d.querySelectorAll('input')].map(i => i.getAttribute('placeholder') || '');
                }"""
            )
            print("  获取工厂 inputs:", json.dumps(inputs, ensure_ascii=False))
            # 按工厂代码 1200 搜索
            code_input = dlg.locator("input").first
            await code_input.fill("1200")
            btn = dlg.locator("button:has-text('搜索'), button:has-text('搜 索'), button:has-text('查询')").first
            print("  搜索按钮 count:", await btn.count())
            if await btn.count():
                await btn.click()
                await page.wait_for_timeout(3000)
            rows = dlg.locator(".el-table__body-wrapper tbody tr")
            print("  工厂结果行:", await rows.count())
            if await rows.count():
                print("  首行:", (await rows.first.inner_text())[:120].replace("\n", " | "))
                await rows.first.click()
                await page.wait_for_timeout(800)
                ok = dlg.locator("button:has-text('确认'), button:has-text('确 定')").first
                print("  确认按钮 count:", await ok.count())
                if await ok.count():
                    await ok.click()
                    await page.wait_for_timeout(1500)
            fval = await page.locator(".el-form-item:has-text('BOE工厂') input").first.get_attribute("value")
            print("  工厂字段值:", fval)

        print("\n== 再点新增 ==")
        await page.locator(ADD_LINE).first.click()
        for i in range(5):
            await page.wait_for_timeout(1000)
            state = await dialog_state(page)
            print(f"  +{i+1}s {state}")
            if '"inputs":0' not in state and "采购凭证查询" in state:
                break
        # 弹窗开了就验证搜索区
        pop = page.locator(".el-dialog[aria-label='采购凭证查询']:visible")
        if await pop.count():
            inputs = await page.evaluate(
                """() => {
                    const d = [...document.querySelectorAll('.el-dialog')].find(x => x.getAttribute('aria-label')==='采购凭证查询' && x.offsetParent);
                    return [...d.querySelectorAll('input')].map(i => i.getAttribute('placeholder') || '');
                }"""
            )
            print("  采购凭证查询 inputs:", json.dumps(inputs, ensure_ascii=False))
        await page.screenshot(path="scripts/_tmp_after_add.png")
        print("截图: scripts/_tmp_after_add.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
