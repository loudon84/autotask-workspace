"""Official-portal login probe. Credentials from env. Never print the password."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"),
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.async_api import async_playwright

from nodeskclaw_rpa_engine.runtime.official_srm_login import login_official_srm

OUT = ROOT / "runtime-cache" / "official-login-probe"
SELECTORS = {
    "username": "input[placeholder='账号或手机号码']:visible",
    "password": "input[type='password']:visible",
    "captcha": "input[placeholder='验证码']:visible",
    "captcha_image": ".el-form-item:has(input[placeholder='验证码']) img:visible",
    "agreement": ".userAgree .el-checkbox:visible .el-checkbox__inner, .userAgree .el-checkbox:visible",
    "login_button": "button:has-text('登录'):visible",
    "login_error": ".el-message--error",
    "login_success": ".el-menu-item:has-text('订单'):visible, span:has-text('订单'):visible",
}


class RecordingEvents:
    def __init__(self) -> None:
        self.items: list[dict] = []

    async def emit(self, type, message="", payload=None, **kwargs):  # noqa: A002
        self.items.append({"type": type, "message": message, "payload": payload or {}})


class QuietLog:
    async def info(self, message, extra=None):
        safe = dict(extra or {})
        safe.pop("text", None)
        print("log", message, json.dumps(safe, ensure_ascii=False), flush=True)


def selector(name, **values):
    value = SELECTORS[name]
    for key, replacement in values.items():
        value = value.replace(f"{{{key}}}", str(replacement))
    return value


async def main() -> int:
    url = (os.environ.get("OFFICIAL_OCR_URL") or "").strip()
    username = (os.environ.get("OFFICIAL_OCR_USER") or "").strip()
    password = os.environ.get("OFFICIAL_OCR_PASS") or ""
    if not url or not username or not password:
        print("missing_env")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        ctx = SimpleNamespace(
            page=page,
            credentials={"username": username, "password": password},
            selectors=SELECTORS,
            events=RecordingEvents(),
            portal_url=url,
            artifacts=None,
            log=QuietLog(),
        )
        try:
            await login_official_srm(ctx, selector=selector)
        except Exception as exc:
            code = getattr(exc, "code", "")
            await page.screenshot(path=str(OUT / "probe-failed.png"), full_page=True)
            print("login_failed", type(exc).__name__, code, str(exc)[:240], flush=True)
            await browser.close()
            return 1
        agreed_box = page.locator(".userAgree .el-checkbox:visible").first
        agreed = await agreed_box.count()
        checked = False
        if agreed:
            classes = await agreed_box.get_attribute("class")
            checked = "is-checked" in (classes or "")
        success = await page.locator(SELECTORS["login_success"]).first.is_visible()
        attempts = None
        reused = False
        for item in ctx.events.items:
            if item["type"] == "STEP_SUCCEEDED":
                payload = item.get("payload") or {}
                attempts = payload.get("captchaAttempts")
                reused = bool(payload.get("reusedSession"))
        await page.screenshot(path=str(OUT / "probe-success.png"), full_page=True)
        print(
            json.dumps(
                {
                    "ok": bool(success),
                    "agreementChecked": checked,
                    "url": page.url,
                    "captchaAttempts": attempts,
                    "reusedSession": reused,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        await browser.close()
        return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
