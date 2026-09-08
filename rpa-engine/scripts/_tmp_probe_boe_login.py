"""临时：探测京东方 SRM 登录页真实 DOM（输入框/按钮属性）。用完即删。"""

import asyncio

from playwright.async_api import async_playwright


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel="chrome")
        page = await browser.new_page()
        await page.goto("https://supply.boe.com/", wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)
        print("URL:", page.url)
        inputs = await page.evaluate(
            """() => Array.from(document.querySelectorAll('input')).map(el => ({
                type: el.getAttribute('type'),
                placeholder: el.getAttribute('placeholder'),
                name: el.getAttribute('name'),
                id: el.id,
                cls: el.className,
                visible: !!(el.offsetWidth || el.offsetHeight),
            }))"""
        )
        for i in inputs:
            print("input:", i)
        buttons = await page.evaluate(
            """() => Array.from(document.querySelectorAll('button')).map(el => ({
                text: (el.innerText || '').trim().slice(0, 20),
                type: el.getAttribute('type'),
                cls: (el.className || '').slice(0, 60),
                visible: !!(el.offsetWidth || el.offsetHeight),
            }))"""
        )
        for b in buttons:
            print("button:", b)
        await browser.close()


asyncio.run(main())
