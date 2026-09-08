"""临时探针 v12：正确定位行内「原产国/地区」select，验证选项与选择。

用法：uv run python scripts/_tmp_probe_region3.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from playwright.async_api import async_playwright

sys.path.insert(0, r"d:\work_space260811\autotask-workspace\rpa-engine\src")
from nodeskclaw_rpa_engine.runtime.boe_srm import (  # noqa: E402
    login_boe_srm,
    open_invoice_packing,
    prepare_invoice_create,
)

SESSION = Path(
    r"d:\work_space260811\autotask-workspace\rpa-engine\runtime-cache\sessions"
    r"\a3668cbaf0893c4e9651e1b67765b8fc19518dfd9c068a83453b51e3adac67f4\storage_state.json"
)
SEL = json.loads(
    Path(r"d:\work_space260811\autotask-workspace\rpa-flows\rpa_flow_srm_boe_pack_save_draft\1.0.6\selectors.json").read_text(encoding="utf-8")
)

PO = "9100069442"
ITEM = "47-7001373"


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(SESSION))
        page = await context.new_page()
        ctx = SimpleNamespace(
            page=page,
            portal_url="https://supply.boe.com",
            credentials={"username": "V1002012AA", "password": "x"},
        )
        sel = lambda n: SEL[n]
        await login_boe_srm(ctx, selector=sel)
        page = await open_invoice_packing(ctx, selector=sel)
        await page.locator(sel("create_button")).first.click()
        await page.wait_for_timeout(800)
        await prepare_invoice_create(page, selector=sel, factory="1200")

        await page.locator(sel("add_line_button")).first.click()
        await page.locator(sel("popup")).first.wait_for(timeout=10000)
        await page.locator(sel("po_input")).first.fill(PO)
        await page.locator(sel("item_input")).first.fill(ITEM)
        await page.locator(sel("popup_search_button")).first.click()
        await page.wait_for_timeout(1200)
        await page.locator(sel("popup_checkbox")).first.click()
        await page.locator(sel("popup_save")).first.click()
        try:
            await page.locator(sel("popup")).first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        await page.wait_for_timeout(1500)

        # 精确定位：含「原产国」表头的那张表 → 其 body 行 → 该列 td
        info = await page.evaluate(
            """() => {
                const tables = [...document.querySelectorAll('.el-table')]
                    .filter(t => !t.closest('.el-dialog'));
                for (let ti = 0; ti < tables.length; ti++) {
                    const t = tables[ti];
                    const ths = [...t.querySelectorAll('.el-table__header-wrapper th')].map(th => th.textContent.trim());
                    const idx = ths.findIndex(h => h.includes('原产国'));
                    if (idx < 0) continue;
                    const row = t.querySelector('.el-table__body-wrapper tbody tr');
                    if (!row) continue;  // 表头克隆表没有行，跳过
                    const tds = [...row.querySelectorAll('td')];
                    const td = tds[idx];
                    return {
                        tableIndex: ti, regionIdx: idx, ths,
                        rowCells: tds.length,
                        regionTd: td ? {
                            text: td.textContent.trim().slice(0, 40),
                            inputPh: td.querySelector('input')?.getAttribute('placeholder') || '',
                            inputValue: td.querySelector('input')?.value || '',
                            hasSelect: !!td.querySelector('.el-select'),
                        } : null,
                    };
                }
                return {err: 'not found'};
            }"""
        )
        print("=== 原产国列定位 ===")
        print(json.dumps(info, ensure_ascii=False, indent=1)[:1800])

        ti = info.get("tableIndex")
        idx = info.get("regionIdx")
        if ti is None:
            await browser.close()
            return

        # 用 JS 给该 td 一个临时 id，再用 Playwright 点（绕开复杂作用域选择器）
        await page.evaluate(
            """([ti, idx]) => {
                const tables = [...document.querySelectorAll('.el-table')].filter(t => !t.closest('.el-dialog'));
                const t = tables[ti];
                const row = t.querySelector('.el-table__body-wrapper tbody tr');
                const td = [...row.querySelectorAll('td')][idx];
                const input = td.querySelector('input');
                input.setAttribute('data-probe-region', '1');
            }""",
            [ti, idx],
        )
        region_input = page.locator("input[data-probe-region='1']")
        await region_input.scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        before = await region_input.input_value()
        print("点击前原产国值:", repr(before))
        await region_input.click()
        await page.wait_for_timeout(1200)
        opts = await page.evaluate(
            """() => [...document.querySelectorAll('.el-select-dropdown')]
                .filter(d => d.offsetParent)
                .flatMap(d => [...d.querySelectorAll('.el-select-dropdown__item')])
                .map(li => ({text: li.textContent.trim(), visible: !!li.offsetParent}))"""
        )
        print("下拉选项:", json.dumps(opts, ensure_ascii=False))

        opt = page.locator(".el-select-dropdown__item:has-text('中国台湾'):visible")
        if await opt.count():
            await opt.first.click()
            await page.wait_for_timeout(600)
            after = await region_input.input_value()
            print("选择后原产国值:", repr(after))
        else:
            print("!! 下拉没有 中国台湾")
        await page.screenshot(path="scripts/_tmp_region3.png")
        await browser.close()


asyncio.run(main())
