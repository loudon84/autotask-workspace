"""One-off: inspect login page DOM. No login attempt. UTF-8 safe."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"),
)

SCRIPTS = Path(__file__).resolve().parent
ENGINE_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import probe_tiandy_prod_readonly as probe
from playwright.async_api import async_playwright

OUT_DIR = ENGINE_ROOT / "runtime-cache" / "captcha-probe"

AUTH_CHROME = [
    ".el-menu-item:has-text('订单')",
    "span:has-text('订单')",
    "a:has-text('订单')",
    ".el-menu-item:has-text('主页')",
    "span:has-text('个人中心')",
    "a:has-text('个人中心')",
]
CAPTCHA_SEL = ".el-form-item:has(input[placeholder='验证码']) img:visible"


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser, context, page, label = await probe.launch_browser(pw, headless=True)
        await page.goto("https://supplier.tiandy.com", wait_until="domcontentloaded")
        for wait_s in (3, 7, 15):
            await page.wait_for_timeout(wait_s * 1000 if wait_s == 3 else (wait_s - 7 if wait_s > 7 else 4) * 1000)
            captcha = page.locator(CAPTCHA_SEL)
            n = await captcha.count()
            print(f"t={wait_s}s url={page.url} captcha_visible={n}")
            if n:
                break
        print("final url:", page.url)
        for sel in AUTH_CHROME:
            loc = page.locator(sel)
            n = await loc.count()
            vis = 0
            texts = []
            for i in range(n):
                try:
                    if await loc.nth(i).is_visible():
                        vis += 1
                        if len(texts) < 3:
                            texts.append((await loc.nth(i).inner_text()).strip()[:30])
                except Exception:
                    pass
            print(f"{'HIT' if vis else 'ok '} {sel} count={n} visible={vis} texts={texts}")
        # dump login form area html
        form = page.locator("form").first
        if await form.count():
            html = await form.inner_html()
            (OUT_DIR / "login-form.html").write_text(html, encoding="utf-8")
            print("saved login-form.html len=", len(html))
        await page.screenshot(path=str(OUT_DIR / "login-page-now.png"), full_page=True)
        await browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
