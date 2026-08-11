import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


PORTAL_URL = "http://192.168.102.247:3000/"
DETAIL_URL = (
    "http://192.168.102.247:3000/"
    "#/supplier/pend-orders/POJS2607130002"
)
ENGINE_ENV = Path(
    r"D:\AutoTask-Workspace\nodeskclaw-rpa-engine\.env"
)
SCREENSHOT = Path(__file__).with_name("order-detail.png")

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
    result: dict[str, str] = {}
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
    stem = stem.rsplit(".", maxsplit=1)[0].casefold()
    return CAPTCHA_CODES[stem]


async def main() -> None:
    env = read_env()
    username = env["MOCK_SRM_USERNAME"]
    password = env["MOCK_SRM_PASSWORD"]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=True,
        )
        page = await browser.new_page(viewport={"width": 1600, "height": 1000})
        await page.goto(PORTAL_URL, wait_until="domcontentloaded")
        captcha = page.locator("img[data-rpa='login-captcha-image']")
        await captcha.wait_for(state="visible", timeout=10_000)
        code = captcha_code(await captcha.get_attribute("src"))
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
            timeout=10_000,
        )

        await page.goto(DETAIL_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1_000)
        await page.screenshot(path=str(SCREENSHOT), full_page=True)

        snapshot = await page.evaluate(
            """() => {
              const attrs = (el) => {
                const result = {};
                for (const name of [
                  'data-rpa', 'id', 'name', 'type', 'placeholder',
                  'class', 'role', 'aria-label', 'readonly', 'disabled'
                ]) {
                  if (el.hasAttribute(name)) result[name] = el.getAttribute(name);
                }
                return result;
              };
              const compact = (value) =>
                String(value || '').replace(/\\s+/g, ' ').trim().slice(0, 500);
              return {
                title: document.title,
                url: location.href,
                scripts: performance.getEntriesByType('resource')
                  .map((entry) => entry.name)
                  .filter((name) => name.includes('.js')),
                dataRpa: [...document.querySelectorAll('[data-rpa]')].map((el) => ({
                  tag: el.tagName.toLowerCase(),
                  attrs: attrs(el),
                  text: compact(el.innerText),
                })),
                inputs: [...document.querySelectorAll('input, textarea')].map((el) => ({
                  tag: el.tagName.toLowerCase(),
                  attrs: attrs(el),
                  value: compact(el.value),
                })),
                buttons: [...document.querySelectorAll('button')].map((el) => ({
                  attrs: attrs(el),
                  text: compact(el.innerText),
                })),
                tables: [...document.querySelectorAll('table')].map((table) => ({
                  headers: [...table.querySelectorAll('thead th')].map((el) =>
                    compact(el.innerText)
                  ),
                  rows: [...table.querySelectorAll('tbody tr')].map((row) =>
                    [...row.querySelectorAll('td')].map((el) => compact(el.innerText))
                  ),
                })),
              };
            }"""
        )
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
