"""One-off: load official SRM login page and capture the captcha image."""

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
sys.path.insert(0, str(ENGINE_ROOT / "src"))
sys.path.insert(0, str(SCRIPTS))

from playwright.async_api import async_playwright

import probe_tiandy_prod_readonly as probe

OUT_DIR = ENGINE_ROOT / "runtime-cache" / "captcha-probe"


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        headless = os.environ.get("PROBE_HEADLESS", "1") == "1"
        browser, context, page, label = await probe.launch_browser(playwright, headless=headless)
        print(f"headless={headless}")
        print(f"browser={label}")
        await page.goto("https://supplier.tiandy.com", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        captcha = page.locator(
            ".el-form-item:has(input[placeholder='验证码']) img:visible"
        ).first
        if await captcha.count() == 0:
            await page.screenshot(path=str(OUT_DIR / "login-page.png"), full_page=True)
            print("captcha image not visible; saved login-page.png")
            await browser.close()
            return 2
        await page.screenshot(path=str(OUT_DIR / "login-page.png"), full_page=True)
        from PIL import Image

        samples: list[Image.Image] = []
        for i in range(10):
            png = OUT_DIR / f"sample-{i}.png"
            await captcha.screenshot(path=str(png))
            samples.append(Image.open(png).convert("RGB"))
            if i < 9:
                await captcha.click()
                await page.wait_for_timeout(900)
        scale = 4
        w, h = samples[0].size
        montage = Image.new("RGB", (w * scale, h * scale * len(samples)), "white")
        for i, img in enumerate(samples):
            montage.paste(img.resize((w * scale, h * scale), Image.NEAREST), (0, i * h * scale))
        montage.save(OUT_DIR / "montage.png")
        print(f"saved montage.png with {len(samples)} samples, size={montage.size}")
        await browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
