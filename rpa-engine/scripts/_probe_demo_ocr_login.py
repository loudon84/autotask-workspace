"""Demo-portal login using OCR only (no filename captcha map).

Credentials come from env set by the service wrapper. Never print them.
"""
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

SELECTORS = {
    "username": "[data-rpa='login-username']",
    "password": "[data-rpa='login-password']",
    "captcha": "[data-rpa='login-captcha']",
    "captcha_image": "img[data-rpa='login-captcha-image']",
    "agreement": "[data-rpa='login-agreement'] input[type='checkbox']",
    "login_button": "button[data-rpa='login-submit']",
    "login_error": ".el-message--error",
    "login_success": "[data-rpa='portal-env-tag']",
}


class RecordingEvents:
    def __init__(self) -> None:
        self.items: list[dict] = []

    async def emit(self, type, message="", payload=None, **kwargs):
        self.items.append({"type": type, "message": message, "payload": payload or {}})


class QuietLog:
    async def info(self, message, extra=None):
        safe = dict(extra or {})
        safe.pop("text", None)
        print("log", message, json.dumps(safe, ensure_ascii=False))


def selector(name, **values):
    value = SELECTORS[name]
    for key, replacement in values.items():
        value = value.replace(f"{{{key}}}", str(replacement))
    return value


async def main() -> int:
    url = (os.environ.get("DEMO_OCR_URL") or "").strip()
    username = (os.environ.get("DEMO_OCR_USER") or "").strip()
    password = os.environ.get("DEMO_OCR_PASS") or ""
    if not url or not username or not password:
        print("missing_env")
        return 2

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
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
            print("login_failed", type(exc).__name__, code, str(exc)[:240])
            await browser.close()
            return 1
        success = await page.locator(SELECTORS["login_success"]).is_visible()
        attempts = None
        for item in ctx.events.items:
            if item["type"] == "STEP_SUCCEEDED":
                attempts = (item.get("payload") or {}).get("captchaAttempts")
        print(
            json.dumps(
                {
                    "ok": bool(success),
                    "url": page.url,
                    "captchaAttempts": attempts,
                    "usedFilenameMap": False,
                },
                ensure_ascii=False,
            )
        )
        await browser.close()
        return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
