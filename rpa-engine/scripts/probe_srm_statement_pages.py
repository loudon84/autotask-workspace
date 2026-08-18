"""只读探测演示 SRM 收货页/对账页的 data-rpa 与表头。不打印凭据。"""

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

PAGE_PROBE_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const rpa = [...document.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa'));
  const tables = [...document.querySelectorAll('.el-table')].map((table) => ({
    headers: [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.textContent)),
    rowCount: table.querySelectorAll('.el-table__body-wrapper tbody tr').length,
    firstRowButtons: [...(table.querySelector('.el-table__body-wrapper tbody tr')?.querySelectorAll('[data-rpa]') || [])]
      .map((el) => el.getAttribute('data-rpa')),
  }));
  const buttons = [...document.querySelectorAll('button')].map((btn) => ({
    text: clean(btn.innerText),
    rpa: btn.getAttribute('data-rpa'),
  })).filter((item) => item.text || item.rpa).slice(0, 40);
  return { url: location.href, hash: location.hash, rpa: [...new Set(rpa)].slice(0, 80), tables, buttons };
}"""


def resolve_captcha_code(image_src: str | None) -> str | None:
    if not image_src:
        return None
    clean = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


def load_credentials() -> tuple[str, str, str]:
    portal_url = os.environ.get("SUPPLIER_PORTAL_URL", "").strip()
    username = os.environ.get("SUPPLIER_PORTAL_USERNAME", "").strip()
    password = os.environ.get("SUPPLIER_PORTAL_PASSWORD", "")
    if portal_url and username and password:
        return portal_url, username, password
    settings = Settings()
    username = (settings.mock_srm_username.get_secret_value() if settings.mock_srm_username else "") or ""
    password = (settings.mock_srm_password.get_secret_value() if settings.mock_srm_password else "") or ""
    portal_url = portal_url or "http://192.168.102.247:3000"
    if not username or not password:
        raise SystemExit("缺少门户凭据：请设置 SUPPLIER_PORTAL_* 或 Engine MOCK_SRM_USERNAME/PASSWORD")
    return portal_url, username, password


async def probe_hash(page, portal_root: str, hash_path: str) -> dict:
    await page.goto(f"{portal_root}/#{hash_path.lstrip('#')}", wait_until="domcontentloaded")
    await page.wait_for_timeout(1800)
    return await page.evaluate(PAGE_PROBE_JS)


async def main() -> int:
    portal_url, username, password = load_credentials()
    portal_root = portal_url.split("#", 1)[0].rstrip("/")
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
            print("login=ok")
            for hash_path in ("/supplier/receivings", "/finance/reconciliation"):
                result = await probe_hash(page, portal_root, hash_path)
                print(f"== {hash_path} ==")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            row_sample = await page.evaluate(
                """() => {
                  const clean = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
                  const table = document.querySelector("[data-rpa='reconciliation-table'] .el-table, [data-rpa='reconciliation-page'] .el-table");
                  if (!table) return null;
                  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.textContent));
                  const rows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')].slice(0, 3).map((tr) => {
                    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
                    const row = {};
                    headers.forEach((h, i) => { if (h) row[h] = cells[i] || ''; });
                    return row;
                  });
                  return rows;
                }"""
            )
            print("== reconciliation rows ==")
            print(json.dumps(row_sample, ensure_ascii=False, indent=2))
            recv_rows = await page.evaluate(
                """() => {
                  const clean = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
                  return null;
                }"""
            )
            await page.goto(f"{portal_root}/#/supplier/receivings", wait_until="domcontentloaded")
            await page.wait_for_timeout(1200)
            recv_sample = await page.evaluate(
                """() => {
                  const clean = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
                  const table = document.querySelector("[data-rpa='receiving-list-page'] .el-table");
                  if (!table) return null;
                  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.textContent));
                  const rows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')].slice(0, 2).map((tr) => {
                    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
                    const row = {};
                    headers.forEach((h, i) => { if (h) row[h] = cells[i] || ''; });
                    row._rpa = tr.getAttribute('data-rpa') || [...tr.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa')).join(',');
                    return row;
                  });
                  const range = document.querySelector("[data-rpa='receiving-date-range']");
                  return {
                    rows,
                    dateInputs: range ? [...range.querySelectorAll('input')].map((el) => el.getAttribute('placeholder') || el.className) : [],
                  };
                }"""
            )
            print("== receiving rows ==")
            print(json.dumps(recv_sample, ensure_ascii=False, indent=2))
            await page.goto(f"{portal_root}/#/finance/reconciliation", wait_until="domcontentloaded")
            await page.wait_for_timeout(1200)
            first = page.locator("[data-rpa^='reconciliation-payable-']:visible").first
            if await first.count():
                await first.click()
                await page.wait_for_timeout(1800)
                detail = await page.evaluate(PAGE_PROBE_JS)
                print("== payable detail ==")
                print(json.dumps(detail, ensure_ascii=False, indent=2))
            return 0
        finally:
            await browser.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
