from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from captcha_adapter import resolve_demo_captcha
from nodeskclaw_rpa_sdk.errors import RpaBusinessError, RpaHumanRequiredError


async def run(ctx):
    page = ctx.page
    selectors = ctx.selectors
    username = ctx.credentials["username"]
    password = ctx.credentials["password"]

    ctx.log.info("Opening the SRM login page")
    await page.goto(ctx.portal_url, wait_until="domcontentloaded")
    await page.locator(selectors["login_username"]).wait_for(state="visible")

    captcha_src = await page.locator(
        selectors["login_captcha_image"]
    ).get_attribute("src")
    captcha_code = resolve_demo_captcha(captcha_src)
    if captcha_code is None:
        await ctx.artifacts.screenshot("captcha_human_required")
        raise RpaHumanRequiredError("CAPTCHA_REQUIRED")

    await page.locator(selectors["login_username"]).fill(username)
    await page.locator(selectors["login_password"]).fill(password)
    await page.locator(selectors["login_captcha"]).fill(captcha_code)

    agreement = page.locator(selectors["login_agreement"])
    if not await agreement.is_checked():
        await agreement.check()

    await page.locator(selectors["login_submit"]).click()

    try:
        await page.locator(selectors["login_success"]).wait_for(
            state="visible", timeout=10_000
        )
    except PlaywrightTimeoutError as exc:
        await ctx.artifacts.screenshot("login_failed")
        error = page.locator(selectors["login_error"])
        reason = await error.first.text_content() if await error.count() else None
        ctx.log.warning("SRM login failed", extra={"portal_reason": reason})
        raise RpaBusinessError("LOGIN_FAILED") from exc

    await ctx.artifacts.screenshot("login_succeeded")
    ctx.log.info("SRM login completed")

    return {"authenticated": True}
