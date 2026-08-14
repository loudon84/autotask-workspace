"""SRM 门户只读探测：列表页结构、保存按钮、回复状态。

只读取 DOM，不执行任何写操作（不填日期、不保存、不签章、不下载）。
凭据只从进程环境读取：SUPPLIER_PORTAL_URL / SUPPLIER_PORTAL_USERNAME / SUPPLIER_PORTAL_PASSWORD。

用法：
    $env:SUPPLIER_PORTAL_URL = "http://192.168.102.247:3000"
    $env:SUPPLIER_PORTAL_USERNAME = "..."
    $env:SUPPLIER_PORTAL_PASSWORD = "..."
    .\\.venv\\Scripts\\python.exe scripts\\probe_srm_portal_readonly.py
"""

import asyncio
import json
import os
import re
import sys

from playwright.async_api import async_playwright

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


def resolve_captcha_code(image_src: str | None) -> str | None:
    if not image_src:
        return None
    clean = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


LIST_PROBE_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const page = document.querySelector("[data-rpa='order-list-page']");
  if (!page) return { error: 'order-list-page not found', url: location.href };
  const tables = [...page.querySelectorAll('.el-table')].map((table) => {
    const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.textContent));
    const rows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')].map((tr) => ({
      rpa: tr.getAttribute('data-rpa'),
      cells: [...tr.querySelectorAll('td')].map((td) => clean(td.textContent)),
      tags: [...tr.querySelectorAll('.el-tag')].map((t) => clean(t.textContent)),
      buttons: [...tr.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa')),
    }));
    return { headers, rowCount: rows.length, rows: rows.slice(0, 20) };
  });
  const pagination = page.querySelector('.el-pagination');
  return {
    url: location.href,
    tables,
    pagination: pagination ? clean(pagination.textContent) : null,
    filters: [...page.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa')).slice(0, 50),
  };
}"""

DETAIL_PROBE_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const root = document.querySelector("[data-rpa='order-detail-page'], [data-rpa='pend-order-detail-page']");
  if (!root) return { error: 'detail page not found', url: location.href };
  const rpaAttrs = [...root.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa'));
  const saveBtn = root.querySelector("[data-rpa='pend-order-detail-save-btn'], [data-rpa='order-detail-save-btn']");
  const signBtn = root.querySelector("[data-rpa='pend-order-detail-sign-btn'], [data-rpa='order-detail-sign-btn']");
  const dateInputs = [...root.querySelectorAll("[data-rpa^='pend-order-detail-expected-date-']")].map((el) => el.getAttribute('data-rpa'));
  const tags = [...root.querySelectorAll('.order-summary .el-tag')].map((t) => clean(t.textContent));
  return {
    url: location.href,
    rootAttr: root.getAttribute('data-rpa'),
    tags,
    saveButton: saveBtn ? { visible: !!saveBtn.offsetParent, disabled: saveBtn.disabled } : null,
    signButton: signBtn ? { visible: !!signBtn.offsetParent, disabled: signBtn.disabled } : null,
    dateInputCount: dateInputs.length,
    dateInputs: dateInputs.slice(0, 10),
    rpaAttrs: [...new Set(rpaAttrs)].slice(0, 80),
  };
}"""


async def main() -> int:
    portal_url = os.environ.get("SUPPLIER_PORTAL_URL", "").strip()
    username = os.environ.get("SUPPLIER_PORTAL_USERNAME", "").strip()
    password = os.environ.get("SUPPLIER_PORTAL_PASSWORD", "")
    if not portal_url or not username or not password:
        print("缺少 SUPPLIER_PORTAL_URL / SUPPLIER_PORTAL_USERNAME / SUPPLIER_PORTAL_PASSWORD")
        return 2

    async with async_playwright() as pw:
        channel = os.environ.get("PROBE_BROWSER_CHANNEL", "chromium")
        browser = await pw.chromium.launch(channel=channel, headless=True)
        page = await browser.new_page()
        try:
            await page.goto(portal_url, wait_until="domcontentloaded")
            captcha = page.locator("img[data-rpa='login-captcha-image']")
            await captcha.wait_for(state="visible", timeout=10000)
            code = resolve_captcha_code(await captcha.get_attribute("src"))
            if code is None:
                print("验证码无法解析，需要人工")
                return 3
            await page.fill("[data-rpa='login-username']", username)
            await page.fill("[data-rpa='login-password']", password)
            await page.fill("[data-rpa='login-captcha']", code)
            agreement = page.locator("[data-rpa='login-agreement'] input[type='checkbox']")
            if not await agreement.is_checked():
                await agreement.check()
            await page.click("button[data-rpa='login-submit']")
            await page.wait_for_selector("[data-rpa='portal-env-tag']", timeout=10000)
            print("== 登录成功 ==")

            await page.goto(f"{portal_url}/#/supplier/orders", wait_until="domcontentloaded")
            await page.wait_for_selector("[data-rpa='order-list-page']", timeout=10000)
            await page.wait_for_timeout(1500)
            list_result = await page.evaluate(LIST_PROBE_JS)
            print("== 列表页 ==")
            print(json.dumps(list_result, ensure_ascii=False, indent=2))

            rows = list_result.get("tables", [{}])[0].get("rows", []) if list_result.get("tables") else []
            target_po = None
            for row in rows:
                for attr in row.get("buttons") or []:
                    match = re.match(r"order-detail-(.+)", attr or "")
                    if match and "待签章" in (row.get("tags") or []):
                        target_po = match.group(1)
                        break
                if target_po:
                    break
            if target_po is None:
                for row in rows:
                    for attr in row.get("buttons") or []:
                        match = re.match(r"order-detail-(.+)", attr or "")
                        if match:
                            target_po = match.group(1)
                            break
                    if target_po:
                        break
            if target_po:
                detail_btn = page.locator(f"[data-rpa='order-detail-{target_po}']:visible")
                if await detail_btn.count():
                    await detail_btn.first.click()
                    await page.wait_for_selector(
                        "[data-rpa='order-detail-page'], [data-rpa='pend-order-detail-page']",
                        timeout=10000,
                    )
                    await page.wait_for_timeout(1500)
                    detail_result = await page.evaluate(DETAIL_PROBE_JS)
                    print(f"== 详情页（{target_po}，只读） ==")
                    print(json.dumps(detail_result, ensure_ascii=False, indent=2))
            else:
                print("列表页没有可探测的订单行")
            return 0
        finally:
            await browser.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
