"""临时：删除探针草稿 PROBE-REGION-001，释放 PO 数量。

用法：uv run python scripts/_tmp_probe_clean.py
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
)

SESSION = Path(
    r"d:\work_space260811\autotask-workspace\rpa-engine\runtime-cache\sessions"
    r"\a3668cbaf0893c4e9651e1b67765b8fc19518dfd9c068a83453b51e3adac67f4\storage_state.json"
)
SEL = json.loads(
    Path(r"d:\work_space260811\autotask-workspace\rpa-flows\rpa_flow_srm_boe_pack_save_draft\1.0.6\selectors.json").read_text(encoding="utf-8")
)


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

        # 不带条件直接看列表前几行（找 PROBE 草稿的真实流水号）
        await page.locator(sel("list_search_button")).first.click()
        await page.wait_for_timeout(1500)
        dump = await page.evaluate(
            """() => [...document.querySelectorAll('.invoice-list .el-table__body-wrapper tbody tr')]
                .slice(0, 5)
                .map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent.trim().slice(0, 22)))"""
        )
        print("列表前5行:")
        for r in dump:
            print(" ", json.dumps(r, ensure_ascii=False))
        rows = page.locator(sel("list_row"), has_text="PROBE-REGION-001")
        n = await rows.count()
        print("含 PROBE-REGION-001 的行:", n)
        if not n:
            await page.screenshot(path="scripts/_tmp_clean.png")
            await browser.close()
            return
        # 行按钮 dump
        dump = await page.evaluate(
            """() => {
                const tr = document.querySelector('.invoice-list .el-table__body-wrapper tbody tr');
                if (!tr) return null;
                return {
                    cells: [...tr.querySelectorAll('td')].map(td => td.textContent.trim().slice(0, 24)),
                    buttons: [...tr.querySelectorAll('button')].map(b => ({text: b.textContent.trim(), disabled: b.disabled})),
                };
            }"""
        )
        print(json.dumps(dump, ensure_ascii=False, indent=1))

        # 点行进详情找删除
        await rows.first.click()
        await page.wait_for_timeout(1500)
        btns = await page.evaluate(
            """() => [...document.querySelectorAll('button')]
                .filter(b => b.offsetParent)
                .map(b => b.textContent.trim())
                .filter(t => t && t.length < 12)"""
        )
        print("详情页按钮:", json.dumps(btns, ensure_ascii=False))
        del_btn = page.locator("button:has-text('删除'):visible")
        if await del_btn.count():
            await del_btn.first.click()
            await page.wait_for_timeout(800)
            confirm = page.locator(".el-message-box button:has-text('确定')")
            if await confirm.count():
                await confirm.first.click()
                await page.wait_for_timeout(1500)
            print("已点删除")
            toasts = await page.evaluate(
                """() => [...document.querySelectorAll('.el-message')].map(m => (m.textContent||'').trim())"""
            )
            print("toast:", json.dumps(toasts, ensure_ascii=False))
        else:
            print("详情页没有删除按钮")
        await page.screenshot(path="scripts/_tmp_clean.png")
        await browser.close()


asyncio.run(main())
