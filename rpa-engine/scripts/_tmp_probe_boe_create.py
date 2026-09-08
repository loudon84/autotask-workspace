"""临时探针 v3：定位「项目信息-新增」按钮为什么 disabled。

走到发票箱单新建页，dump 表单项结构，然后试：填供应商发票号 → 选 BOE 工厂，
每步后看「新增」是否解禁。不点任何保存/提交。

用法：uv run python scripts/_tmp_probe_boe_create.py
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


async def add_line_enabled(page) -> bool:
    btn = page.locator(ADD_LINE).first
    disabled = await btn.get_attribute("disabled")
    cls = await btn.get_attribute("class") or ""
    enabled = disabled is None and "is-disabled" not in cls
    print(f"  新增按钮: disabled={disabled} enabled={enabled}")
    return enabled


async def dump_form(page, label: str) -> None:
    print(f"\n--- 表单项 ({label}) ---")
    items = await page.evaluate(
        """() => [...document.querySelectorAll('.el-form-item')].map(f => {
            const lab = f.querySelector('label');
            const input = f.querySelector('input');
            return {
                label: lab ? lab.textContent.trim() : '',
                required: !!(lab && lab.className.includes('is-required')),
                placeholder: input ? (input.getAttribute('placeholder') || '') : '',
                value: input ? input.value : '',
                disabled: input ? input.disabled : null,
                readonly: input ? input.readOnly : null,
            };
        }).filter(x => x.label).slice(0, 40)"""
    )
    for item in items:
        print("  ", json.dumps(item, ensure_ascii=False))


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
    print("create page url:", page.url)
    return page


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(SESSION))
        page = await walk_to_create(context, await context.new_page())

        await dump_form(page, "刚进新建页")
        await add_line_enabled(page)

        print("\n== 启用AI识别 区域结构 ==")
        ai_html = await page.evaluate(
            """() => {
                const f = [...document.querySelectorAll('.el-form-item')]
                    .find(x => (x.querySelector('label')||{}).textContent?.includes('启用AI识别'));
                return f ? f.querySelector('.el-form-item__content')?.innerHTML?.slice(0, 600) : 'not found';
            }"""
        )
        print(" ", ai_html)

        print("\n== 点「启用AI识别-否」 ==")
        ai_no = page.locator(
            ".el-form-item:has-text('启用AI识别') .el-radio:has-text('否'), "
            ".el-form-item:has-text('启用AI识别') .el-radio-button:has-text('否')"
        ).first
        print("  否 选项 count:", await ai_no.count())
        if await ai_no.count():
            await ai_no.click()
            await page.wait_for_timeout(2000)
            print("  已点 否")
        await add_line_enabled(page)

        print("\n== 试填供应商发票号 ==")
        inv = page.locator(".el-form-item:has-text('供应商发票号') input").first
        if await inv.count():
            disabled = await inv.get_attribute("disabled")
            print("  发票号输入框 disabled:", disabled)
            if disabled is None:
                await inv.fill("PROBE-TEST-001")
                print("  已填 PROBE-TEST-001")
        await add_line_enabled(page)

        print("\n== 试选 BOE 工厂 ==")
        factory = page.locator(".el-form-item:has-text('BOE工厂') input").first
        print("  工厂输入框 count:", await factory.count())
        if await factory.count():
            await factory.click()
            await page.wait_for_timeout(2000)
            dialogs = await page.evaluate(
                """() => [...document.querySelectorAll('.el-dialog')]
                    .map(d => ({aria: d.getAttribute('aria-label'), visible: !!(d.offsetParent)}))
                    .filter(d => d.visible)"""
            )
            print("  点击后可见弹窗:", json.dumps(dialogs, ensure_ascii=False))
            # 弹窗里搜 1200 选首行
            dlg = page.locator(".el-dialog:visible").last
            if await dlg.count():
                search_input = dlg.locator("input[placeholder*='工厂']").first
                print("  工厂搜索框 count:", await search_input.count())
                if await search_input.count():
                    await search_input.fill("1200")
                    btn = dlg.locator("button:has-text('搜索'), button:has-text('搜 索'), button:has-text('查询')").first
                    if await btn.count():
                        await btn.click()
                        await page.wait_for_timeout(3000)
                    rows = dlg.locator(".el-table__body-wrapper tbody tr")
                    print("  工厂结果行:", await rows.count())
                    if await rows.count():
                        await rows.first.click()
                        await page.wait_for_timeout(1500)
        await add_line_enabled(page)

        print("\n== 项目信息「新增」→ 采购凭证查询弹窗 ==")
        await page.locator(ADD_LINE).first.click()
        await page.wait_for_timeout(3000)
        popup = page.locator(".el-dialog[aria-label='采购凭证查询']")
        print("  弹窗 count:", await popup.count())
        if await popup.count():
            dump = await page.evaluate(
                """() => {
                    // 所有 dialog 概览
                    const dialogs = [...document.querySelectorAll('.el-dialog')].map(d => ({
                        aria: d.getAttribute('aria-label'),
                        visible: !!(d.offsetParent),
                        inputs: d.querySelectorAll('input').length,
                        tables: d.querySelectorAll('.el-table').length,
                        buttons: [...d.querySelectorAll('button')].map(b => (b.textContent||'').trim()).filter(t=>t).slice(0,8),
                    }));
                    // 找 placeholder 含 采购订单 的 input 的祖先链
                    const poInput = [...document.querySelectorAll('input')].find(i => (i.getAttribute('placeholder')||'').includes('采购订单'));
                    let chain = [];
                    if (poInput) {
                        let el = poInput;
                        for (let i = 0; i < 8 && el; i++) {
                            chain.push({
                                tag: el.tagName.toLowerCase(),
                                class: String(el.className && el.className.baseVal === undefined ? el.className : '').slice(0, 60),
                                aria: el.getAttribute ? (el.getAttribute('aria-label') || '') : '',
                            });
                            el = el.parentElement;
                        }
                    }
                    return { dialogs, poInputFound: !!poInput, poPlaceholder: poInput ? poInput.getAttribute('placeholder') : '', chain };
                }"""
            )
            print("  dialogs:", json.dumps(dump["dialogs"], ensure_ascii=False))
            print("  poInputFound:", dump["poInputFound"], "placeholder:", dump["poPlaceholder"])
            print("  po input 祖先链:", json.dumps(dump["chain"], ensure_ascii=False))
            for name, sel in {
                "po_input": "input[placeholder*='采购订单号']",
                "item_input": "input[placeholder*='物料编码']",
                "search_btn": "button:has-text('搜索'), button:has-text('搜 索')",
            }.items():
                loc = popup.locator(sel)
                print(f"  {name}: count={await loc.count()}")
            await popup.locator("input[placeholder*='采购订单号']").first.fill("9100048919")
            await popup.locator("button:has-text('搜索'), button:has-text('搜 索')").first.click()
            await page.wait_for_timeout(4000)
            rows = popup.locator(".el-table > .el-table__body-wrapper tbody tr")
            print("  结果行数:", await rows.count())
            if await rows.count():
                print("  首行:", (await rows.first.inner_text())[:200].replace("\n", " | "))
            chk = popup.locator(".el-table__fixed-header-wrapper th.el-table-column--selection .el-checkbox__inner")
            print("  全选 checkbox count:", await chk.count())
            save = popup.locator(".avue-crud__menu button:has-text('保存')")
            print("  保存按钮 count:", await save.count())
            # 不点保存，直接关弹窗
            await popup.locator(".el-dialog__headerbtn").first.click()

        await page.screenshot(path="scripts/_tmp_create_page.png", full_page=False)
        print("\n截图: scripts/_tmp_create_page.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
