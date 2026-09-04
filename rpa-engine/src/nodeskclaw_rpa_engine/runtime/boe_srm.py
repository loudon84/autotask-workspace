"""京东方 SRM 登录与发票箱单导航。一期不处理邮箱验证码。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from nodeskclaw_rpa_engine.runtime.errors import RpaBusinessError, RpaFatalError

# @lat: [[runtime#BOE SRM login]]


def _clean(value: Any) -> str:
    return str(value or "").strip()


async def _visible(locator: Any) -> bool:
    try:
        return bool(await locator.first.is_visible())
    except Exception:
        return False


async def login_boe_srm(ctx: Any, *, selector: Callable[..., str]) -> None:
    page = ctx.page
    credentials = ctx.credentials if isinstance(ctx.credentials, Mapping) else {}
    username = _clean(credentials.get("username"))
    password = str(credentials.get("password", ""))
    if not username or not password:
        raise RpaFatalError("BOE_CREDENTIALS_MISSING", "京东方门户账号或密码缺失")

    url = str(getattr(page, "url", "") or "")
    if "dashboard" in url or "bsrm.boe.com" in url:
        otp = page.locator(selector("otp_dialog"))
        if await _visible(otp):
            raise RpaBusinessError(
                "BOE_OTP_REQUIRED",
                "出现邮箱验证码。请先在 SRM 网页登录 AA/AD 账号后再跑 AutoTask。",
            )
        return

    await page.goto(ctx.portal_url, wait_until="domcontentloaded")
    otp = page.locator(selector("otp_dialog"))
    if await _visible(otp):
        raise RpaBusinessError(
            "BOE_OTP_REQUIRED",
            "出现邮箱验证码。请先在 SRM 网页登录 AA/AD 账号后再跑 AutoTask。",
        )
    await page.locator(selector("username")).first.fill(username)
    await page.locator(selector("password")).first.fill(password)
    await page.locator(selector("login_button")).first.click()
    await page.wait_for_timeout(1500)
    if await _visible(otp):
        raise RpaBusinessError(
            "BOE_OTP_REQUIRED",
            "出现邮箱验证码。请先在 SRM 网页登录 AA/AD 账号后再跑 AutoTask。",
        )


async def open_invoice_packing(ctx: Any, *, selector: Callable[..., str]) -> None:
    """从导航点击进入，禁止 goto 单据 URL。"""
    page = ctx.page
    current = str(getattr(page, "url", "") or "")
    if "ticket=" in current:
        raise RpaFatalError("BOE_TICKET_URL_FORBIDDEN", "禁止把 ticket URL 写进导航")
    await page.locator(selector("nav_delivery")).first.click()
    await page.wait_for_timeout(800)
    await page.locator(selector("nav_invoice_packing")).first.click()
    await page.wait_for_timeout(1200)
