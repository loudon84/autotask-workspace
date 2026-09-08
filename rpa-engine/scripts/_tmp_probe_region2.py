"""临时探针 v11：行级原产国(地区)怎么填 + 附件行怎么删 + 完整保存验证。

用法：uv run python scripts/_tmp_probe_region2.py
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
OUT = Path(r"d:\work_space260811\autotask-workspace\rpa-engine\scripts\_tmp_region2_out.txt")
lines_out: list[str] = []


def log(*args) -> None:
    msg = " ".join(str(a) for a in args)
    lines_out.append(msg)
    print(msg)


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

        # 头表填满（发票号/三个日期/总体积）
        await page.locator(sel("invoice_no")).first.fill("PROBE-REGION-001")
        for name in ("invoice_date", "etd", "consign_date"):
            await page.locator(sel(name)).first.fill("2026-09-07")
            await page.keyboard.press("Tab")
        tv = page.locator(sel("total_vol")).first
        await tv.click(force=True)
        await tv.press("Control+a")
        await page.keyboard.type("0.06534", delay=20)
        await tv.press("Tab")

        # 加一行
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

        # 1. 找行表里「原产国」列的控件
        dump = await page.evaluate(
            """() => {
                const tables = [...document.querySelectorAll('.el-card:has(.el-table) .el-table')];
                for (const t of tables) {
                    const ths = [...t.querySelectorAll('.el-table__header-wrapper th')].map(th => th.textContent.trim());
                    const regionIdx = ths.findIndex(h => h.includes('原产国'));
                    if (regionIdx < 0) continue;
                    const row = t.querySelector('.el-table__body-wrapper tbody tr');
                    if (!row) return {err: 'no row', ths};
                    const tds = [...row.querySelectorAll('td')];
                    const td = tds[regionIdx];
                    return {
                        thsCount: ths.length, regionIdx, regionHeader: ths[regionIdx],
                        tdCount: tds.length,
                        regionTdHtml: td ? td.innerHTML.slice(0, 600) : null,
                        // 所有可编辑单元格(有 input/select 的)
                        editable: tds.map((x, i) => ({
                            i, header: ths[i] || '',
                            inputs: [...x.querySelectorAll('input')].map(inp => inp.getAttribute('placeholder') || inp.className.slice(0,30)),
                            select: x.querySelectorAll('.el-select').length,
                        })).filter(x => x.inputs.length || x.select),
                    };
                }
                return {err: 'no region table'};
            }"""
        )
        log("=== 行表原产国列 ===")
        log(json.dumps(dump, ensure_ascii=False, indent=1)[:2500])

        # 2. 试填原产国：点该单元格的 select，抓下拉选项
        region_cell = page.locator(
            ".el-card:has-text('项目信息') .el-table__body-wrapper tbody tr td"
        )
        idx = dump.get("regionIdx")
        if idx is not None:
            cell = region_cell.nth(idx)
            await cell.scroll_into_view_if_needed()
            await cell.click()
            await page.wait_for_timeout(1000)
            opts = await page.evaluate(
                """() => [...document.querySelectorAll('.el-select-dropdown')]
                    .filter(d => d.offsetParent)
                    .flatMap(d => [...d.querySelectorAll('.el-select-dropdown__item')])
                    .map(li => li.textContent.trim())"""
            )
            log("原产国下拉选项:", json.dumps(opts, ensure_ascii=False))
            # 点「中国台湾」
            opt = page.locator(".el-select-dropdown:visible >> .el-select-dropdown__item:has-text('中国台湾')")
            if await opt.count():
                await opt.first.click()
                log("已选 中国台湾")
            else:
                log("下拉里没有 中国台湾!")
            await page.wait_for_timeout(500)

        # 3. 附件表：删除按钮真实状态 + 删双签PO/协议行
        att = await page.evaluate(
            """() => {
                const card = [...document.querySelectorAll('.el-card')].find(x => x.textContent.includes('附件信息'));
                if (!card) return {err: 'no att card'};
                return [...card.querySelectorAll('.el-table__body-wrapper tbody tr')].map(tr => {
                    const tds = [...tr.querySelectorAll('td')];
                    const btn = tr.querySelector('button');
                    const sel = tr.querySelector('.el-select input');
                    return {
                        no: tds[0]?.textContent.trim(),
                        typeValue: sel ? sel.value : (tds[1]?.textContent.trim() || ''),
                        btnDisabled: btn ? btn.disabled : null,
                        btnAria: btn ? btn.getAttribute('aria-disabled') : null,
                        btnCls: btn ? btn.className : null,
                    };
                });
            }"""
        )
        log("=== 附件行 ===")
        log(json.dumps(att, ensure_ascii=False, indent=1))

        # 删双签PO/协议行：逐行找类型含「双签」的，点其删除
        att_rows = page.locator(".el-card:has-text('附件信息') .el-table__body-wrapper tbody tr")
        n = await att_rows.count()
        log("附件行数:", n)
        for i in range(n - 1, -1, -1):
            r = att_rows.nth(i)
            val = await r.locator("input").first.input_value() if await r.locator("input").count() else ""
            if "双签" in str(val):
                btn = r.locator("button:has-text('删除')")
                await btn.first.click(force=True)
                await page.wait_for_timeout(800)
                # 可能有确认框
                confirm = page.locator(".el-message-box button:has-text('确定'), .el-popconfirm button:has-text('确定')")
                if await confirm.count():
                    await confirm.first.click()
                    await page.wait_for_timeout(500)
                log(f"已删附件行 {i} ({val})")

        # 4. 点保存，抓 toast + 是否拿到流水号
        await page.locator(sel("save_button")).first.click()
        await page.wait_for_timeout(3000)
        toasts = await page.evaluate(
            """() => [...document.querySelectorAll('.el-message, .el-message-box, .el-notification')]
                .map(m => (m.textContent||'').trim()).filter(t => t)"""
        )
        log("=== 保存后 toast ===")
        log(json.dumps(toasts, ensure_ascii=False))
        body = await page.content()
        import re
        m = re.search(r"(?:发票箱单流水号|流水号)[:：\s]*([A-Za-z0-9\-]+)", body)
        log("流水号:", m.group(1) if m else "未找到")
        await page.screenshot(path="scripts/_tmp_region2.png", full_page=True)
        await browser.close()
        OUT.write_text("\n".join(lines_out), encoding="utf-8")


asyncio.run(main())
