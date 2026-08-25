"""只读：对账列表点查询前后的行数据。不打印凭据。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expandvars(
    r"%LOCALAPPDATA%\ms-playwright"
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from playwright.async_api import async_playwright

from nodeskclaw_rpa_engine.core.config import Settings

CAPTCHA_CODES = {
    "code01": "mp3s",
    "code02": "0ada",
    "code03": "sez0",
    "code04": "ggmh",
    "code05": "rpyt",
    "code06": "y5na",
    "code07": "elhx",
    "code08": "el0m",
    "code09": "aqh9",
    "code10": "gqcy",
}

DUMP_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const page = document.querySelector("[data-rpa='reconciliation-page']");
  const rpa = [...document.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa'));
  const dateInputs = [...document.querySelectorAll("[data-rpa='reconciliation-page'] input")]
    .map((el) => ({
      placeholder: el.getAttribute('placeholder'),
      rpa: el.closest('[data-rpa]')?.getAttribute('data-rpa') || null,
      value: el.value,
    })).slice(0, 12);
  const table = document.querySelector("[data-rpa='reconciliation-page'] .el-table");
  if (!table) {
    return { hash: location.hash, rpa: [...new Set(rpa)].slice(0, 60), dateInputs, error: 'table_missing' };
  }
  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.innerText));
  const rows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')].slice(0, 8).map((tr) => {
    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
    const row = {};
    headers.forEach((h, i) => { if (h) row[h] = cells[i] || ''; });
    row._rpa = [...tr.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa'));
    return row;
  });
  return {
    hash: location.hash,
    rpa: [...new Set(rpa)].slice(0, 60),
    dateInputs,
    headers,
    rowCount: table.querySelectorAll('.el-table__body-wrapper tbody tr').length,
    rows,
  };
}"""

FIND_JS = r"""({checkDate, checkAmount}) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const norm = (value) => clean(value).replace(/,/g, '').replace(/[¥￥元]/g, '');
  const page = document.querySelector("[data-rpa='reconciliation-page']");
  if (!page) return { error: 'page_missing' };
  const table = page.querySelector('.el-table');
  if (!table) return { error: 'table_missing' };
  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.innerText));
  const dateIdx = headers.findIndex((h) => h.includes('对账日期'));
  const amountIdx = headers.findIndex((h) => h.includes('对账总额'));
  const samples = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')].slice(0, 5).map((tr) => {
    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
    return { date: cells[dateIdx] || '', amount: cells[amountIdx] || '', rpa: [...tr.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa')) };
  });
  for (const tr of table.querySelectorAll('.el-table__body-wrapper tbody tr')) {
    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
    const dateText = clean(cells[dateIdx] || '').replace(/\//g, '-');
    const amountText = norm(cells[amountIdx] || '');
    if (dateText.startsWith(checkDate) && amountText === norm(checkAmount)) {
      const payable = [...tr.querySelectorAll('[data-rpa^="reconciliation-payable-"]')]
        .map((el) => el.getAttribute('data-rpa'))[0];
      return { rpa: payable || null, dateIdx, amountIdx, samples, matched: true };
    }
  }
  return { error: 'not_found', dateIdx, amountIdx, samples };
}"""


def resolve_captcha_code(image_src: str | None) -> str | None:
    if not image_src:
        return None
    clean = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


def dump(label: str, payload: object) -> None:
    print(f"== {label} ==")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


async def fill_date(page, index: int, value: str) -> None:
    inputs = page.locator("[data-rpa='reconciliation-page'] .el-date-editor input")
    locator = inputs.nth(index)
    await locator.click()
    try:
        await locator.fill(value)
    except Exception:
        await locator.evaluate(
            """(el, v) => {
              el.removeAttribute('readonly');
              el.value = v;
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            value,
        )


async def main() -> int:
    settings = Settings()
    username = (settings.mock_srm_username.get_secret_value() if settings.mock_srm_username else "") or ""
    password = (settings.mock_srm_password.get_secret_value() if settings.mock_srm_password else "") or ""
    portal_url = "http://192.168.102.247:3000"
    if not username or not password:
        print("missing credentials")
        return 2
    portal_root = portal_url.rstrip("/")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(portal_root, wait_until="domcontentloaded")
            captcha = page.locator("img[data-rpa='login-captcha-image']")
            await captcha.wait_for(state="visible", timeout=10000)
            code = resolve_captcha_code(await captcha.get_attribute("src"))
            if code is None:
                print("captcha_unresolved")
                return 3
            await page.fill("[data-rpa='login-username']", username)
            await page.fill("[data-rpa='login-password']", password)
            await page.fill("[data-rpa='login-captcha']", code)
            agreement = page.locator("[data-rpa='login-agreement'] input[type='checkbox']")
            if not await agreement.is_checked():
                await agreement.check()
            await page.click("button[data-rpa='login-submit']")
            await page.wait_for_selector("[data-rpa='portal-env-tag']", timeout=15000)
            await page.goto(f"{portal_root}/#/finance/reconciliation", wait_until="domcontentloaded")
            await page.locator("[data-rpa='reconciliation-page']").wait_for(state="visible", timeout=15000)
            dump("before_search", await page.evaluate(DUMP_JS))
            search = page.locator("[data-rpa='reconciliation-search-btn']")
            await search.click()
            await page.wait_for_timeout(1500)
            dump("after_search_empty_dates", await page.evaluate(DUMP_JS))
            dump(
                "payable_buttons",
                await page.evaluate(
                    """() => {
                      const clean = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
                      return [...document.querySelectorAll('[data-rpa^="reconciliation-payable-"]')].slice(0, 6).map((el) => {
                        const rect = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        return {
                          rpa: el.getAttribute('data-rpa'),
                          tag: el.tagName,
                          text: clean(el.innerText),
                          className: el.className,
                          parent: el.parentElement ? el.parentElement.tagName + '.' + el.parentElement.className : '',
                          tablePart: el.closest('.el-table__fixed-right') ? 'fixed-right'
                            : el.closest('.el-table__fixed') ? 'fixed-left'
                            : el.closest('.el-table__body-wrapper') ? 'body'
                            : 'other',
                          visible: style.visibility,
                          display: style.display,
                          opacity: style.opacity,
                          width: Math.round(rect.width),
                          height: Math.round(rect.height),
                          href: el.getAttribute('href'),
                        };
                      });
                    }"""
                ),
            )
            dump(
                "payable_layout",
                await page.evaluate(
                    """() => {
                      const all = [...document.querySelectorAll('[data-rpa^="reconciliation-payable-"]')];
                      const byPart = {};
                      for (const el of all) {
                        const part = el.closest('.el-table__fixed-right') ? 'fixed-right'
                          : el.closest('.el-table__fixed') ? 'fixed-left'
                          : el.closest('.el-table__body-wrapper') ? 'body'
                          : 'other';
                        byPart[part] = (byPart[part] || 0) + 1;
                      }
                      const texts = [...document.querySelectorAll('button, a, span')].filter((el) => (el.innerText || '').includes('收货应付')).slice(0, 4).map((el) => ({
                        tag: el.tagName,
                        text: (el.innerText || '').trim(),
                        rpa: el.getAttribute('data-rpa'),
                        tablePart: el.closest('.el-table__fixed-right') ? 'fixed-right'
                          : el.closest('.el-table__fixed') ? 'fixed-left'
                          : el.closest('.el-table__body-wrapper') ? 'body'
                          : 'other',
                        visible: getComputedStyle(el).visibility,
                      }));
                      return {
                        payableCount: all.length,
                        byPart,
                        hasFixedRight: Boolean(document.querySelector('.el-table__fixed-right')),
                        texts,
                      };
                    }"""
                ),
            )
            await fill_date(page, 0, "2026-08-18")
            await fill_date(page, 1, "2026-08-18")
            await page.keyboard.press("Enter")
            await search.click()
            await page.wait_for_timeout(1500)
            dump("after_search_with_date", await page.evaluate(DUMP_JS))
            dump(
                "match_after_date",
                await page.evaluate(FIND_JS, {"checkDate": "2026-08-18", "checkAmount": "1151309.12"}),
            )
            return 0
        finally:
            await browser.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
