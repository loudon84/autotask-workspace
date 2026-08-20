"""Official SRM login with OCR. Used by scheduled/repeated Flows.

Does not wait for a human. Failed OCR raises a retryable error so the next
timer tick or Runtime retry can try a fresh CAPTCHA.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import re
from collections.abc import Callable, Mapping
from typing import Any

from nodeskclaw_rpa_engine.runtime.captcha_ocr import recognize_captcha
from nodeskclaw_rpa_engine.runtime.errors import (
    RpaBusinessError,
    RpaFatalError,
    RpaRetryableError,
)
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

MAX_CAPTCHA_ATTEMPTS = 3
_CLEAN = re.compile(r"\s+")


def _clean(value: Any) -> str:
    return _CLEAN.sub(" ", str(value or "")).strip()


def is_captcha_error(reason: str | None) -> bool:
    text = (reason or "").casefold()
    return "验证码" in (reason or "") or "captcha" in text


async def capture_captcha_bytes(captcha_image: Any) -> bytes:
    try:
        data_url = await captcha_image.evaluate(
            """
            image => {
              if (typeof image.src === 'string' && image.src.startsWith('data:image')) {
                return image.src;
              }
              const canvas = document.createElement('canvas');
              canvas.width = image.naturalWidth || image.width;
              canvas.height = image.naturalHeight || image.height;
              canvas.getContext('2d').drawImage(image, 0, 0);
              return canvas.toDataURL('image/png');
            }
            """
        )
        if isinstance(data_url, str) and data_url.startswith("data:image"):
            _header, _, b64 = data_url.partition(",")
            if b64:
                return base64.b64decode(b64)
    except (ValueError, TypeError, IndexError, binascii.Error, Exception):
        pass
    return await captcha_image.screenshot(type="png", timeout=5000)


async def _wait_for_captcha_refresh(captcha_image: Any, previous_src: str | None) -> None:
    for _ in range(30):
        current_src = await captcha_image.get_attribute("src")
        if current_src and current_src != previous_src:
            return
        await asyncio.sleep(0.1)


async def _screenshot(ctx: Any, name: str, step_id: str) -> None:
    artifacts = getattr(ctx, "artifacts", None)
    if artifacts is None:
        return
    try:
        await artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return


async def _emit(ctx: Any, event_type: str, message: str, payload: dict[str, Any]) -> None:
    try:
        await ctx.events.emit(event_type, message=message, payload=payload)
    except Exception:
        return


async def _redact_login_fields(page: Any, selector: Callable[..., str]) -> None:
    for name in ("username", "password", "captcha"):
        try:
            await page.fill(selector(name), "")
        except Exception:
            continue


async def login_official_srm(ctx: Any, *, selector: Callable[..., str]) -> None:
    step_id = "srm.login"
    page = ctx.page
    credentials = ctx.credentials if isinstance(ctx.credentials, Mapping) else {}
    username = _clean(credentials.get("username"))
    password = str(credentials.get("password", ""))
    if not username or not password:
        raise RpaFatalError(
            "SRM_CREDENTIALS_MISSING",
            "Supplier portal credentials are unavailable",
        )
    await _emit(
        ctx,
        "STEP_STARTED",
        "Logging in to supplier portal",
        {"stepId": step_id, "stepType": step_id},
    )
    try:
        already = page.locator(selector("login_success"))
        captcha_probe = page.locator(selector("captcha_image"))
        if await already.is_visible() and not await captcha_probe.is_visible():
            await _emit(
                ctx,
                "STEP_SUCCEEDED",
                "Supplier portal session already authenticated",
                {"stepId": step_id, "reusedSession": True},
            )
            return
    except Exception:
        pass

    await page.goto(ctx.portal_url, wait_until="domcontentloaded")
    captcha_image = page.locator(selector("captcha_image"))
    success = page.locator(selector("login_success"))
    try:
        for _ in range(50):
            if await captcha_image.is_visible():
                break
            if await success.is_visible() and not await captcha_image.is_visible():
                await _emit(
                    ctx,
                    "STEP_SUCCEEDED",
                    "Supplier portal session already authenticated",
                    {"stepId": step_id, "reusedSession": True},
                )
                return
            await page.wait_for_timeout(200)
        else:
            await captcha_image.wait_for(state="visible", timeout=1000)
    except Exception as exc:
        raise RpaRetryableError(
            "SRM_LOGIN_PAGE_UNAVAILABLE",
            "Supplier portal login page could not be loaded",
        ) from exc

    await page.fill(selector("username"), username)
    await page.fill(selector("password"), password)
    agreement = page.locator(selector("agreement"))
    try:
        if not await agreement.is_checked():
            await agreement.check()
    except Exception:
        pass

    last_reason = "CAPTCHA_OCR_FAILED"
    for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
        captcha_src = await captcha_image.get_attribute("src")
        try:
            await captcha_image.wait_for(state="visible", timeout=5000)
            image_bytes = await capture_captcha_bytes(captcha_image)
        except Exception:
            last_reason = "CAPTCHA_IMAGE_UNAVAILABLE"
            await page.wait_for_timeout(400)
            continue
        try:
            ocr_result = await asyncio.to_thread(recognize_captcha, image_bytes)
        except RuntimeError as exc:
            if "CAPTCHA_OCR_UNAVAILABLE" in str(exc):
                raise RpaFatalError(
                    "CAPTCHA_OCR_UNAVAILABLE",
                    "Supplier portal CAPTCHA OCR is not installed on the Engine",
                ) from exc
            raise
        except Exception as exc:
            raise RpaFatalError(
                "CAPTCHA_OCR_UNAVAILABLE",
                "Supplier portal CAPTCHA OCR is not installed on the Engine",
            ) from exc

        try:
            await ctx.log.info(
                "Captcha OCR completed",
                {"attempt": attempt, "accepted": ocr_result.accepted},
            )
        except Exception:
            pass

        if not ocr_result.accepted:
            last_reason = ocr_result.rejection_reason or "OCR_LENGTH_INVALID"
            if attempt < MAX_CAPTCHA_ATTEMPTS:
                try:
                    await captcha_image.click()
                    await _wait_for_captcha_refresh(captcha_image, captcha_src)
                except Exception:
                    await page.wait_for_timeout(400)
                continue
            break

        try:
            await page.fill(selector("captcha"), ocr_result.text)
            await page.click(selector("login_button"), timeout=8000)
            outcome, reason = await _wait_for_login_result(page, selector)
        except PlaywrightTimeoutError:
            last_reason = "SRM_LOGIN_TIMEOUT"
            try:
                await page.keyboard.press("Escape")
                await captcha_image.click()
                await _wait_for_captcha_refresh(captcha_image, captcha_src)
            except Exception:
                await page.wait_for_timeout(400)
            continue
        if outcome == "success":
            await _emit(
                ctx,
                "STEP_SUCCEEDED",
                "Supplier portal login completed",
                {"stepId": step_id, "captchaAttempts": attempt},
            )
            return
        if outcome == "timeout":
            last_reason = "SRM_LOGIN_TIMEOUT"
            continue
        if outcome == "error" and is_captcha_error(reason):
            last_reason = "CAPTCHA_OCR_FAILED"
            if attempt < MAX_CAPTCHA_ATTEMPTS:
                try:
                    await _wait_for_captcha_refresh(captcha_image, captcha_src)
                except Exception:
                    await page.wait_for_timeout(400)
                continue
            break
        await _redact_login_fields(page, selector)
        raise RpaBusinessError("SRM_LOGIN_FAILED", "Supplier portal login failed")

    await _screenshot(ctx, "official-portal-captcha-ocr-failed", step_id)
    await _redact_login_fields(page, selector)
    raise RpaRetryableError(
        last_reason if last_reason.startswith("CAPTCHA") or last_reason.startswith("OCR") else "CAPTCHA_OCR_FAILED",
        "Supplier portal CAPTCHA could not be recognized",
    )


async def _wait_visible(locator: Any, timeout_ms: int) -> bool:
    wait_for = getattr(locator, "wait_for", None)
    if callable(wait_for):
        try:
            await wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False
    deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
    while asyncio.get_event_loop().time() < deadline:
        try:
            if await locator.is_visible():
                return True
        except Exception:
            pass
        await asyncio.sleep(0.2)
    return False


async def _wait_for_login_result(
    page: Any, selector: Callable[..., str]
) -> tuple[str, str | None]:
    success = page.locator(selector("login_success"))
    error = page.locator(selector("login_error"))
    success_task = asyncio.create_task(_wait_visible(success, 15_000))
    error_task = asyncio.create_task(_wait_visible(error, 15_000))
    done, pending = await asyncio.wait(
        {success_task, error_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    if success_task in done and success_task.result():
        return "success", None
    if error_task in done and error_task.result():
        try:
            reason = _clean(await error.first.inner_text())
        except Exception:
            reason = ""
        return "error", reason
    return "timeout", None
