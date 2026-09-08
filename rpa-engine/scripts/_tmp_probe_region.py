"""临时探针 v10：找行级「地区」控件 + 附件表删除控件。

复刻 save_draft 到「加了一行」为止，然后：
1. dump 项目信息行的可编辑控件（找地区/原产地下拉）
2. dump 附件信息表结构与删除按钮
3. 点保存复现校验 toast

用法：uv run python scripts/_tmp_probe_region.py
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

        # 加一行（复刻 _attach_line）
        await page.locator(sel("add_line_button")).first.click()
        await page.locator(sel("popup")).first.wait_for(timeout=10000)
        await page.locator(sel("po_input")).first.fill(PO)
        await page.locator(sel("item_input")).first.fill(ITEM)
        await page.locator(sel("popup_search_button")).first.click()
        await page.wait_for_timeout(1200)
        rows = page.locator(sel("popup_row"))
        print("弹窗结果行:", await rows.count())
        await page.locator(sel("popup_checkbox")).first.click()
        await page.locator(sel("popup_save")).first.click()
        try:
            await page.locator(sel("popup")).first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        await page.wait_for_timeout(1500)

        # 1. 项目信息行结构：列头 + 首行每个 td 里的控件
        dump = await page.evaluate(
            """() => {
                const card = [...document.querySelectorAll('.el-card')]
                    .find(x => x.textContent.includes('项目信息'));
                if (!card) return {err: 'no item card'};
                const headers = [...card.querySelectorAll('.el-table__header-wrapper th')]
                    .map(th => th.textContent.trim());
                const fixedHeaders = [...card.querySelectorAll('.el-table__fixed .el-table__header-wrapper th')]
                    .map(th => th.textContent.trim());
                const row = card.querySelector('.el-table__body-wrapper tbody tr');
                const cells = row ? [...row.querySelectorAll('td')].map(td => ({
                    text: td.textContent.trim().slice(0, 30),
                    inputs: [...td.querySelectorAll('input')].map(i => ({
                        ph: i.getAttribute('placeholder') || '', ro: i.readOnly, dis: i.disabled,
                        ariaDis: i.getAttribute('aria-disabled'),
                    })),
                    selects: td.querySelectorAll('.el-select').length,
                    buttons: [...td.querySelectorAll('button')].map(b => b.textContent.trim()),
                })) : [];
                // 操作列
                const opTd = row ? [...row.querySelectorAll('td')].find(td => td.querySelector('button')) : null;
                return {headers, fixedHeaders, cellCount: cells.length, cells: cells.slice(0, 20)};
            }"""
        )
        print("\n=== 项目信息 ===")
        print(json.dumps(dump, ensure_ascii=False, indent=1)[:3000])

        # 2. 附件信息表结构
        att = await page.evaluate(
            """() => {
                const card = [...document.querySelectorAll('.el-card')]
                    .find(x => x.textContent.includes('附件'));
                if (!card) return {err: 'no attachment card'};
                const headers = [...card.querySelectorAll('.el-table__header-wrapper th')]
                    .map(th => th.textContent.trim());
                const rows = [...card.querySelectorAll('.el-table__body-wrapper tbody tr')].map(tr => ({
                    cells: [...tr.querySelectorAll('td')].map(td => td.textContent.trim().slice(0, 20)),
                    buttons: [...tr.querySelectorAll('button')].map(b => ({
                        text: b.textContent.trim(), cls: (b.className||'').slice(0, 50),
                    })),
                }));
                const menu = [...card.querySelectorAll('.avue-crud__menu button')].map(b => b.textContent.trim());
                return {headers, rowCount: rows.length, rows, menuButtons: menu};
            }"""
        )
        print("\n=== 附件信息 ===")
        print(json.dumps(att, ensure_ascii=False, indent=1)[:2500])

        # 3. 点保存复现校验 toast
        await page.locator(sel("save_button")).first.click()
        await page.wait_for_timeout(2500)
        toasts = await page.evaluate(
            """() => [...document.querySelectorAll('.el-message, .el-message-box, .el-notification')]
                .map(m => (m.textContent||'').trim()).filter(t => t)"""
        )
        print("\n=== 保存后 toast ===")
        print(json.dumps(toasts, ensure_ascii=False))
        # 再读流行是否有变化（错误行标红等）
        await page.screenshot(path="scripts/_tmp_region.png", full_page=True)
        await browser.close()


asyncio.run(main())
