"""临时探针 v7：弹窗保存后，项目信息表回填行的真实结构。

走完整 enrich 路径到弹窗保存，然后 dump 项目信息表的行 innerText/HTML。
不点单据级保存/提交。

用法：uv run python scripts/_tmp_probe_item_row.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

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
PO = "9100069442"
ITEM = "47-7001373"

SEL = json.loads(
    Path(r"d:\work_space260811\autotask-workspace\rpa-flows\rpa_flow_srm_boe_pack_enrich\1.0.2\selectors.json").read_text(encoding="utf-8")
)


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(SESSION))
        page = await context.new_page()
        from types import SimpleNamespace

        ctx = SimpleNamespace(
            page=page,
            portal_url="https://supply.boe.com",
            credentials={"username": "V1002012AA", "password": "x"},
        )
        sel = lambda n: SEL[n]
        await login_boe_srm(ctx, selector=sel)
        page = await open_invoice_packing(ctx, selector=sel)
        await page.locator(sel("create_button")).first.click()
        await page.locator(sel("add_line_button")).first.wait_for(timeout=15000)
        await prepare_invoice_create(page, selector=sel, factory="1200")

        print("== 新增 → 弹窗搜索 ==")
        await page.locator(sel("add_line_button")).first.click()
        await page.locator(sel("popup")).first.wait_for(state="visible", timeout=10000)
        await page.locator(sel("po_input")).first.fill(PO)
        await page.locator(sel("item_input")).first.fill(ITEM)
        await page.locator(sel("search_button")).first.click()
        await page.wait_for_timeout(3000)
        rows = page.locator(sel("popup_row"))
        print("popup rows:", await rows.count())
        await page.locator(sel("popup_checkbox")).first.click()
        await page.locator(sel("popup_save")).first.click()
        try:
            await page.locator(sel("popup")).first.wait_for(state="hidden", timeout=10000)
        except Exception:
            print("弹窗未关闭！")
        await page.wait_for_timeout(2000)

        print("\n== 项目信息表结构 ==")
        data = await page.evaluate(
            """() => {
                const card = [...document.querySelectorAll('.el-card.item-card')]
                    .find(c => c.textContent.includes('项目信息'));
                if (!card) return {err: 'no card'};
                const tables = [...card.querySelectorAll('.el-table')].map((t, ti) => ({
                    ti,
                    cls: t.className.slice(0, 80),
                    rows: [...t.querySelectorAll('tbody tr')].map(tr => tr.innerText.replace(/\\n/g, ' | ').slice(0, 300)),
                }));
                return {tables};
            }"""
        )
        print(json.dumps(data, ensure_ascii=False, indent=1))

        item_rows = page.locator(sel("item_table_row"))
        count = await item_rows.count()
        print("item_table_row count:", count)
        for i in range(count):
            print(f"  row{i}:", (await item_rows.nth(i).inner_text()).replace("\n", " | ")[:300])

        await page.screenshot(path="scripts/_tmp_item_row.png", full_page=True)
        print("截图: scripts/_tmp_item_row.png")
        await browser.close()


asyncio.run(main())
