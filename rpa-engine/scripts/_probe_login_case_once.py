"""One-off: test whether official SRM captcha is case-sensitive.

Alternates lower/upper case submissions of the ddddocr result and reports
which variant (if any) logs in. Read-only otherwise: stops right after login.
"""

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

from nodeskclaw_rpa_engine.runtime.captcha_ocr import get_classifier, parse_ocr_prediction
from playwright.async_api import async_playwright

import probe_tiandy_prod_readonly as probe

SEL_USER = "input[placeholder='账号或手机号码']:visible"
SEL_PASS = "input[type='password']:visible"
SEL_CAPTCHA = "input[placeholder='验证码']:visible"
SEL_CAPTCHA_IMG = ".el-form-item:has(input[placeholder='验证码']) img:visible"
SEL_LOGIN_BTN = "button:has-text('登录'):visible"
SEL_ERROR = ".el-message--error"
SEL_SUCCESS = ".el-menu-item:has-text('订单'):visible, span:has-text('订单'):visible"
OUT_DIR = ENGINE_ROOT / "runtime-cache" / "captcha-probe"

MAX_ATTEMPTS = 10


async def main() -> int:
    probe.load_env_file(probe.ENV_FILE)
    username = os.environ.get("SUPPLIER_PORTAL_USERNAME", "").strip()
    password = os.environ.get("SUPPLIER_PORTAL_PASSWORD", "")
    if not username or not password:
        print("missing SUPPLIER_PORTAL_USERNAME/PASSWORD")
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    engine = get_classifier()

    async with async_playwright() as playwright:
        browser, context, page, label = await probe.launch_browser(playwright, headless=True)
        print(f"browser={label}")
        await page.goto("https://supplier.tiandy.com", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        await page.fill(SEL_USER, username)
        await page.fill(SEL_PASS, password)
        agreement = page.locator(".userAgree .el-checkbox:visible").first
        if await agreement.count():
            cls = (await agreement.get_attribute("class")) or ""
            if "is-checked" not in cls:
                await agreement.evaluate(
                    "el => (el.querySelector('.el-checkbox__inner') || el).click()"
                )

        for attempt in range(1, MAX_ATTEMPTS + 1):
            img = page.locator(SEL_CAPTCHA_IMG).first
            shot = await img.screenshot(type="png", timeout=5000)
            try:
                prediction = engine.classification(shot, probability=True)
            except TypeError:
                prediction = engine.classification(shot)
            result = parse_ocr_prediction(prediction)
            if not result.accepted:
                print(f"attempt {attempt}: rejected {result.text!r} {result.rejection_reason}")
                await img.click()
                await page.wait_for_timeout(900)
                continue
            variant = "upper" if attempt % 2 == 0 else "lower"
            text = result.text.upper() if variant == "upper" else result.text
            (OUT_DIR / f"case-{attempt:02d}-{variant}-{result.text}.png").write_bytes(shot)
            await page.fill(SEL_CAPTCHA, text)
            await page.click(SEL_LOGIN_BTN, timeout=8000)
            ok = False
            err = ""
            for _ in range(40):
                if await page.locator(SEL_SUCCESS).count() > 0:
                    ok = True
                    break
                err_loc = page.locator(SEL_ERROR).first
                if await err_loc.count() > 0:
                    err = (await err_loc.inner_text()).strip()
                    break
                await page.wait_for_timeout(300)
            print(
                f"attempt {attempt}: {variant} {text!r} conf={result.confidence:.3f} "
                f"-> {'LOGIN OK' if ok else 'fail ' + err[:40]}"
            )
            if ok:
                await page.screenshot(path=str(OUT_DIR / "login-success.png"))
                await browser.close()
                return 0
            if "验证码" not in err:
                # Non-captcha error (e.g. password wrong): stop, no point retrying
                print(f"non-captcha error, aborting: {err[:60]}")
                await browser.close()
                return 3
            await page.wait_for_timeout(900)
        await browser.close()
        print("all attempts failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
