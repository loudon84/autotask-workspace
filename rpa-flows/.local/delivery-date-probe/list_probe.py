import asyncio
import json

from playwright.async_api import async_playwright

from probe import CAPTCHA_CODES, PORTAL_URL, read_env


PO_NO = "POJS2607130002"
ORDER_LIST_URL = f"{PORTAL_URL}#/supplier/orders"


def captcha_code(source: str | None) -> str:
    clean = (source or "").split("?", maxsplit=1)[0]
    stem = clean.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    stem = stem.rsplit(".", maxsplit=1)[0].casefold()
    return CAPTCHA_CODES[stem]


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

        await page.goto(ORDER_LIST_URL, wait_until="domcontentloaded")
        await page.locator("[data-rpa='order-list-page']").wait_for(
            state="visible",
            timeout=10_000,
        )
        await page.fill("[data-rpa='order-no-input']", PO_NO)
        await page.click("[data-rpa='order-search-btn']")
        row = page.locator(f"[data-rpa='order-row-{PO_NO}']:visible")
        await row.wait_for(state="visible", timeout=10_000)
        row_snapshot = await row.evaluate(
            """(el) => ({
              text: String(el.innerText || '').replace(/\\s+/g, ' ').trim(),
              dataRpa: [...el.querySelectorAll('[data-rpa]')].map((child) => ({
                tag: child.tagName.toLowerCase(),
                value: child.getAttribute('data-rpa'),
                text: String(child.innerText || '').replace(/\\s+/g, ' ').trim(),
              })),
            })"""
        )
        detail = page.locator(f"[data-rpa='order-detail-{PO_NO}']:visible")
        await detail.wait_for(state="visible", timeout=10_000)
        await detail.click()
        await page.locator("[data-rpa='pend-order-detail-page']").wait_for(
            state="visible",
            timeout=10_000,
        )
        await page.locator(
            "[data-rpa^='pend-order-detail-expected-date-']:visible"
        ).first.wait_for(state="visible", timeout=10_000)
        lines = await page.evaluate(
            """() => [...document.querySelectorAll(
              "[data-rpa^='pend-order-detail-expected-date-']"
            )]
              .filter((el) => el.offsetParent !== null)
              .map((date) => {
                const row = date.closest('tr');
                return {
                  dateRpa: date.getAttribute('data-rpa'),
                  cells: [...row.querySelectorAll(':scope > td')].map((cell) => ({
                    text: String(cell.innerText || '').replace(/\\s+/g, ' ').trim(),
                    dataRpa: [...cell.querySelectorAll('[data-rpa]')]
                      .map((el) => el.getAttribute('data-rpa')),
                  })),
                };
              })"""
        )
        print(
            json.dumps(
                {
                    "listUrl": ORDER_LIST_URL,
                    "row": row_snapshot,
                    "detailUrl": page.url,
                    "detailTitle": await page.title(),
                    "lines": lines,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
