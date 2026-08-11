import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


PORTAL_URL = "http://192.168.102.247:3000/"
PO_NO = "POJS2606030010"
ENGINE_ENV = Path(r"D:\AutoTask-Workspace\nodeskclaw-rpa-engine\.env")
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


def read_env() -> dict[str, str]:
    result = {}
    for raw_line in ENGINE_ENV.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", maxsplit=1)
        result[name.strip()] = value.strip().strip("\"'")
    return result


def captcha_code(source: str | None) -> str:
    clean = (source or "").split("?", maxsplit=1)[0]
    stem = clean.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    return CAPTCHA_CODES[stem.rsplit(".", maxsplit=1)[0].casefold()]


async def main() -> None:
    env = read_env()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=True,
        )
        page = await browser.new_page(viewport={"width": 1600, "height": 1000})
        await page.goto(PORTAL_URL, wait_until="domcontentloaded")
        captcha = page.locator("img[data-rpa='login-captcha-image']")
        await captcha.wait_for(state="visible", timeout=10_000)
        await page.fill("[data-rpa='login-username']", env["MOCK_SRM_USERNAME"])
        await page.fill("[data-rpa='login-password']", env["MOCK_SRM_PASSWORD"])
        await page.fill(
            "[data-rpa='login-captcha']",
            captcha_code(await captcha.get_attribute("src")),
        )
        agreement = page.locator(
            "[data-rpa='login-agreement'] input[type='checkbox']"
        )
        if not await agreement.is_checked():
            await agreement.check()
        await page.click("button[data-rpa='login-submit']")
        await page.locator("[data-rpa='portal-env-tag']").wait_for(
            state="visible",
            timeout=10_000,
        )

        await page.goto(
            f"{PORTAL_URL}#/supplier/orders",
            wait_until="domcontentloaded",
        )
        await page.locator("[data-rpa='order-list-page']").wait_for(
            state="visible",
            timeout=10_000,
        )
        await page.fill("[data-rpa='order-no-input']", PO_NO)
        await page.click("[data-rpa='order-search-btn']")
        await page.locator(f"[data-rpa='order-row-{PO_NO}']:visible").wait_for(
            state="visible",
            timeout=10_000,
        )
        await page.click(f"[data-rpa='order-detail-{PO_NO}']:visible")
        await page.locator(f"[data-rpa='order-detail-no-{PO_NO}']:visible").wait_for(
            state="visible",
            timeout=15_000,
        )
        await page.wait_for_timeout(1_000)

        snapshot = await page.evaluate(
            """() => {
              const clean = (value) =>
                String(value || '').replace(/\\s+/g, ' ').trim();
              return {
                title: document.title,
                url: location.href,
                dataRpa: [...document.querySelectorAll('[data-rpa]')].map((el) => ({
                  tag: el.tagName.toLowerCase(),
                  value: el.getAttribute('data-rpa'),
                  text: clean(el.innerText).slice(0, 300),
                  visible: el.offsetParent !== null,
                })),
                tables: [...document.querySelectorAll('table')].map((table) => ({
                  visible: table.offsetParent !== null,
                  headers: [...table.querySelectorAll('thead th')]
                    .map((el) => clean(el.innerText)),
                  rowCount: table.querySelectorAll('tbody tr').length,
                  firstRow: [...(table.querySelector('tbody tr')
                    ?.querySelectorAll('td') || [])].map((el) => clean(el.innerText)),
                })),
                dialogs: [...document.querySelectorAll('[role=dialog], .el-dialog')]
                  .map((el) => ({
                    text: clean(el.innerText).slice(0, 300),
                    visible: el.offsetParent !== null,
                  })),
                loadingMasks: [...document.querySelectorAll('.el-loading-mask')]
                  .map((el) => ({
                    visible: el.offsetParent !== null,
                  })),
              };
            }"""
        )
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
