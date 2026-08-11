import asyncio
import json
import os
import re
from pathlib import Path

from playwright.async_api import async_playwright


PORTAL_ROOT = "http://192.168.102.247:3000"
PO_NO = "POJS2607130002"
DETAIL_URL = f'{PORTAL_ROOT}/#/supplier/pend-orders/{PO_NO}'
SCREENSHOT_PATH = Path(r"D:\tmp\supplier-delivery-detail.png")

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


def load_dotenv(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def captcha_code(src: str | None) -> str | None:
    if not src:
        return None
    clean = src.split("?", 1)[0].split("#", 1)[0]
    filename = clean.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


async def main() -> None:
    load_dotenv(Path(r"D:\AutoTask-Workspace\nodeskclaw-rpa-engine\.env"))
    username = os.environ.get("MOCK_SRM_USERNAME", "")
    password = os.environ.get("MOCK_SRM_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("Portal credentials are not configured")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel='chrome', headless=True)
        context = await browser.new_context(viewport={"width": 1600, "height": 1000})
        page = await context.new_page()
        await page.goto(PORTAL_ROOT, wait_until="domcontentloaded")

        image = page.locator("img[data-rpa='login-captcha-image']")
        await image.wait_for(state="visible", timeout=15_000)
        code = captcha_code(await image.get_attribute("src"))
        if code is None:
            raise RuntimeError("Unknown CAPTCHA image")

        await page.fill("[data-rpa='login-username']", username)
        await page.fill("[data-rpa='login-password']", password)
        await page.fill("[data-rpa='login-captcha']", code)
        agreement = page.locator(
            "[data-rpa='login-agreement'] input[type='checkbox']"
        )
        if not await agreement.is_checked():
            await agreement.check()
        await page.click("button[data-rpa='login-submit']")
        await page.locator("[data-rpa='portal-env-tag']").wait_for(
            state="visible",
            timeout=15_000,
        )

        await page.goto(DETAIL_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1_500)
        await page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)

        result = await page.evaluate(
            """() => {
              const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
              const attrs = (el) => {
                const output = {};
                for (const attr of el.attributes || []) {
                  if (
                    attr.name === 'class' ||
                    attr.name === 'type' ||
                    attr.name === 'placeholder' ||
                    attr.name === 'data-rpa' ||
                    attr.name === 'name' ||
                    attr.name === 'aria-label' ||
                    attr.name === 'role' ||
                    attr.name.startsWith('data-')
                  ) {
                    output[attr.name] = attr.value;
                  }
                }
                return output;
              };
              const controls = [...document.querySelectorAll(
                'input, button, textarea, select, [contenteditable=true], [role=button]'
              )].map((el, index) => ({
                index,
                tag: el.tagName.toLowerCase(),
                text: clean(el.innerText || el.textContent),
                value: el.value ?? null,
                disabled: Boolean(el.disabled),
                attrs: attrs(el),
                outer: el.outerHTML.slice(0, 600),
              }));
              const tables = [...document.querySelectorAll('table')].map(
                (table, tableIndex) => ({
                  tableIndex,
                  attrs: attrs(table),
                  headers: [...table.querySelectorAll('thead th')].map(
                    (th) => clean(th.innerText || th.textContent)
                  ),
                  rows: [...table.querySelectorAll('tbody tr')].map(
                    (row, rowIndex) => ({
                      rowIndex,
                      text: clean(row.innerText || row.textContent),
                      attrs: attrs(row),
                      cells: [...row.querySelectorAll('td')].map(
                        (cell, cellIndex) => ({
                          cellIndex,
                          text: clean(cell.innerText || cell.textContent),
                          attrs: attrs(cell),
                          controls: [...cell.querySelectorAll(
                            'input, button, textarea, select, [contenteditable=true]'
                          )].map((el) => ({
                            tag: el.tagName.toLowerCase(),
                            text: clean(el.innerText || el.textContent),
                            value: el.value ?? null,
                            disabled: Boolean(el.disabled),
                            attrs: attrs(el),
                            outer: el.outerHTML.slice(0, 600),
                          })),
                        })
                      ),
                    })
                  ),
                })
              );
              const rpa = [...document.querySelectorAll('[data-rpa]')].map((el) => ({
                tag: el.tagName.toLowerCase(),
                text: clean(el.innerText || el.textContent),
                attrs: attrs(el),
              }));
              return {
                title: document.title,
                url: location.href,
                bodyText: clean(document.body.innerText).slice(0, 12000),
                controls,
                tables,
                rpa,
              };
            }"""
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
