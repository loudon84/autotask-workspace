import asyncio
import base64
import binascii

from nodeskclaw_rpa_sdk.errors import (
    RpaBusinessError,
    RpaHumanRequiredError,
    RpaRetryableError,
)
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Error as PlaywrightError

from captcha_ocr import recognize_captcha


MAX_CAPTCHA_ATTEMPTS = 2
OUTCOME_TIMEOUT_SECONDS = 10


async def _wait_for_login_outcome(page, selectors):
    success_task = asyncio.create_task(
        page.locator(selectors["login_success"]).wait_for(state="visible")
    )
    error = page.locator(selectors["login_error"]).first
    error_task = asyncio.create_task(error.wait_for(state="visible"))
    tasks = {success_task, error_task}

    done, pending = await asyncio.wait(
        tasks,
        timeout=OUTCOME_TIMEOUT_SECONDS,
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    if success_task in done and success_task.exception() is None:
        return "success", None
    if error_task in done and error_task.exception() is None:
        return "error", await error.text_content()
    return "timeout", None


def _is_captcha_error(reason: str | None) -> bool:
    normalized = (reason or "").lower()
    return "验证码" in normalized or "captcha" in normalized


async def _wait_for_captcha_refresh(captcha_image, previous_src):
    for _ in range(30):
        current_src = await captcha_image.get_attribute("src")
        if current_src and current_src != previous_src:
            return
        await asyncio.sleep(0.1)


async def _wait_for_error_clear(page, selectors):
    error = page.locator(selectors["login_error"]).first
    try:
        await error.wait_for(state="hidden", timeout=4_000)
    except PlaywrightTimeoutError:
        return


async def _capture_captcha_bytes(captcha_image):
    try:
        data_url = await captcha_image.evaluate(
            """
            image => {
              const canvas = document.createElement('canvas');
              canvas.width = image.naturalWidth;
              canvas.height = image.naturalHeight;
              canvas.getContext('2d').drawImage(image, 0, 0);
              return canvas.toDataURL('image/png');
            }
            """
        )
        if isinstance(data_url, str) and data_url.startswith("data:image/png;base64,"):
            return base64.b64decode(data_url.split(",", 1)[1])
    except (PlaywrightError, ValueError, TypeError, IndexError, binascii.Error):
        pass

    return await captcha_image.screenshot(type="png")


async def run(ctx):
    page = ctx.page
    selectors = ctx.selectors
    username = ctx.credentials["username"]
    password = ctx.credentials["password"]

    ctx.log.info("Opening the SRM login page")
    await page.goto(ctx.portal_url, wait_until="domcontentloaded")
    await page.locator(selectors["login_username"]).wait_for(state="visible")

    await page.locator(selectors["login_username"]).fill(username)
    await page.locator(selectors["login_password"]).fill(password)

    agreement = page.locator(selectors["login_agreement"])
    if not await agreement.is_checked():
        await agreement.check()

    captcha_image = page.locator(selectors["login_captcha_image"])
    for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
        captcha_src = await captcha_image.get_attribute("src")
        captcha_bytes = await _capture_captcha_bytes(captcha_image)

        try:
            ocr_result = await asyncio.to_thread(recognize_captcha, captcha_bytes)
        except Exception as exc:
            await ctx.artifacts.screenshot("captcha_ocr_unavailable")
            raise RpaHumanRequiredError("CAPTCHA_OCR_UNAVAILABLE") from exc

        ctx.log.info(
            "Captcha OCR completed",
            extra={
                "attempt": attempt,
                "accepted": ocr_result.accepted,
                "confidence": round(ocr_result.confidence, 4),
            },
        )
        if not ocr_result.accepted:
            if attempt < MAX_CAPTCHA_ATTEMPTS:
                await captcha_image.click()
                await _wait_for_captcha_refresh(captcha_image, captcha_src)
                continue
            await ctx.artifacts.screenshot("captcha_ocr_uncertain")
            raise RpaHumanRequiredError(
                ocr_result.rejection_reason or "CAPTCHA_OCR_UNCERTAIN"
            )

        await page.locator(selectors["login_captcha"]).fill(ocr_result.text)
        await page.locator(selectors["login_submit"]).click()
        outcome, reason = await _wait_for_login_outcome(page, selectors)

        if outcome == "success":
            await ctx.artifacts.screenshot("login_succeeded")
            ctx.log.info("SRM login completed", extra={"captchaAttempts": attempt})
            return {"authenticated": True, "captchaAttempts": attempt}

        if outcome == "error" and _is_captcha_error(reason):
            if attempt < MAX_CAPTCHA_ATTEMPTS:
                await _wait_for_captcha_refresh(captcha_image, captcha_src)
                await _wait_for_error_clear(page, selectors)
                continue
            await ctx.artifacts.screenshot("captcha_ocr_failed")
            raise RpaHumanRequiredError("CAPTCHA_OCR_FAILED")

        await ctx.artifacts.screenshot("login_failed")
        if outcome == "timeout":
            raise RpaRetryableError("LOGIN_RESULT_TIMEOUT")
        ctx.log.warning("SRM login failed", extra={"portal_reason": reason})
        raise RpaBusinessError("LOGIN_FAILED")

    raise RpaHumanRequiredError("CAPTCHA_OCR_FAILED")
