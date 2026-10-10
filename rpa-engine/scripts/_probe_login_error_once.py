"""One-off: single login attempt, record the exact portal error text.

One captcha OCR + one submit. Writes the toast DOM text to JSON. No retries.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
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
SEL_ANY_MSG = ".el-message"
SEL_SUCCESS = ".el-menu-item:has-text('订单'):visible, span:has-text('订单'):visible"
OUT_DIR = ENGINE_ROOT / "runtime-cache" / "captcha-probe"
OUT_JSON = OUT_DIR / "login-error-once.json"


async def main() -> int:
    probe.load_env_file(probe.ENV_FILE)
    username = os.environ.get("SUPPLIER_PORTAL_USERNAME", "").strip()
    password = os.environ.get("SUPPLIER_PORTAL_PASSWORD", "")
    if not username or not password:
        print("missing SUPPLIER_PORTAL_USERNAME/PASSWORD")
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result: dict = {"at": datetime.now(UTC).isoformat(), "username": username}
    engine = get_classifier()

    async with async_playwright() as playwright:
        browser, context, page, label = await probe.launch_browser(playwright, headless=True)
        result["browser"] = label
        if os.environ.get("LOAD_SESSION", "0") == "1":
            from nodeskclaw_rpa_engine.runtime.session_cache import session_cache_key

            state = (
                ENGINE_ROOT
                / "runtime-cache"
                / "sessions"
                / session_cache_key("https://supplier.tiandy.com", username)
                / "storage_state.json"
            )
            result["storageState"] = str(state)
            if state.is_file():
                await context.close()
                context = await browser.new_context(
                    viewport={"width": 1600, "height": 1000},
                    storage_state=str(state),
                )
                page = await context.new_page()
                result["storageStateLoaded"] = True
        await page.goto("https://supplier.tiandy.com", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        # capture any toast already visible right after page load (e.g. session expired)
        early = page.locator(SEL_ANY_MSG)
        result["toastsOnLoad"] = [
            (await early.nth(i).inner_text()).strip() for i in range(await early.count())
        ]

        await page.fill(SEL_USER, username)
        await page.fill(SEL_PASS, password)
        agreement = page.locator(".userAgree .el-checkbox:visible").first
        if await agreement.count():
            cls = (await agreement.get_attribute("class")) or ""
            if "is-checked" not in cls:
                await agreement.evaluate(
                    "el => (el.querySelector('.el-checkbox__inner') || el).click()"
                )

        img = page.locator(SEL_CAPTCHA_IMG).first
        ocr = None
        tries = []
        for _ in range(6):
            shot = await img.screenshot(type="png", timeout=5000)
            try:
                prediction = engine.classification(shot, probability=True)
            except TypeError:
                prediction = engine.classification(shot)
            ocr = parse_ocr_prediction(prediction)
            tries.append({"text": ocr.text, "confidence": ocr.confidence, "accepted": ocr.accepted})
            if ocr.accepted:
                (OUT_DIR / "login-error-captcha.png").write_bytes(shot)
                break
            await img.click()
            await page.wait_for_timeout(900)
        result["ocrTries"] = tries
        if ocr is None or not ocr.accepted:
            OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False))
            await browser.close()
            return 3

        await page.fill(SEL_CAPTCHA, ocr.text)
        await page.click(SEL_LOGIN_BTN, timeout=8000)

        outcome = "timeout"
        error_text = ""
        for _ in range(40):
            if await page.locator(SEL_SUCCESS).count() > 0:
                outcome = "success"
                break
            err = page.locator(SEL_ERROR).first
            if await err.count() > 0:
                error_text = (await err.inner_text()).strip()
                outcome = "error"
                break
            await page.wait_for_timeout(300)
        result["outcome"] = outcome
        result["errorText"] = error_text
        all_msg = page.locator(SEL_ANY_MSG)
        result["toastsAfter"] = [
            (await all_msg.nth(i).inner_text()).strip() for i in range(await all_msg.count())
        ]
        await page.screenshot(path=str(OUT_DIR / "login-error-once.png"), full_page=True)
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        await browser.close()
        return 0 if outcome == "success" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
