import re
from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaHumanRequiredError,
    RpaRetryableError,
)

CAPTCHA_CODES = {
    "code01": "mp3s",
    "code02": "0ada",
    "code03": "sez0",
    "code04": "ggmh",
    "code05": "rpyt",
    "code06": "y5na",
    "code07": "elhx",
    "code08": "el0m",
    "code09": "aqh9",
    "code10": "gqcy",
}
PO_NUMBER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
OUTPUT_SCHEMA_VERSION = "SRM_CHECK_REPLY_STATUS_OUTPUT_V1"


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_captcha_code(image_src):
    if not isinstance(image_src, str) or not image_src.strip():
        return None
    clean_src = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean_src.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


def validate_input(raw_input):
    value = raw_input if isinstance(raw_input, Mapping) else {}
    po_no = _clean(value.get("po_no")).upper()
    if not PO_NUMBER_PATTERN.fullmatch(po_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Customer purchase order number is missing or invalid",
        )
    return po_no


async def _safe_emit(ctx, event_type, *, level="INFO", message, payload=None):
    try:
        await ctx.events.emit(event_type, level=level, message=message, payload=payload)
    except Exception:
        return


class SupplierPortalReplyStatusAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.page
        self.selectors = ctx.selectors

    def selector(self, name, **values):
        value = self.selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError(
                "FLOW_SELECTOR_MISSING",
                f"Required supplier portal selector is missing: {name}",
            )
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    async def login(self):
        step_id = "srm.login"
        credentials = self.ctx.credentials if isinstance(self.ctx.credentials, Mapping) else {}
        username = _clean(credentials.get("username"))
        password = str(credentials.get("password", ""))
        if not username or not password:
            raise RpaFatalError(
                "SRM_CREDENTIALS_MISSING",
                "Supplier portal credentials are unavailable",
            )
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Logging in to supplier portal",
            payload={"stepId": step_id, "stepType": step_id},
        )
        try:
            already = self.page.locator(self.selector("login_success"))
            captcha_probe = self.page.locator(self.selector("captcha_image"))
            if await already.is_visible() and not await captcha_probe.is_visible():
                await self.ctx.events.emit(
                    "STEP_SUCCEEDED",
                    message="Supplier portal session already authenticated",
                    payload={"stepId": step_id, "reusedSession": True},
                )
                return
        except Exception:
            pass
        await self.page.goto(self.ctx.portal_url, wait_until="domcontentloaded")
        captcha = self.page.locator(self.selector("captcha_image"))
        try:
            success = self.page.locator(self.selector("login_success"))
            for _ in range(50):
                if await captcha.is_visible():
                    break
                if await success.is_visible() and not await captcha.is_visible():
                    await self.ctx.events.emit(
                        "STEP_SUCCEEDED",
                        message="Supplier portal session already authenticated",
                        payload={"stepId": step_id, "reusedSession": True},
                    )
                    return
                await self.page.wait_for_timeout(200)
            else:
                await captcha.wait_for(state="visible", timeout=1000)
            code = resolve_captcha_code(await captcha.get_attribute("src"))
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_LOGIN_PAGE_UNAVAILABLE",
                "Supplier portal login page could not be loaded",
            ) from exc
        if code is None:
            await self._redact_login_fields()
            raise RpaHumanRequiredError(
                "HUMAN_VERIFICATION_REQUIRED",
                "Supplier portal CAPTCHA requires human verification",
            )
        try:
            await self.page.fill(self.selector("username"), username)
            await self.page.fill(self.selector("password"), password)
            await self.page.fill(self.selector("captcha"), code)
            agreement = self.page.locator(self.selector("agreement"))
            if not await agreement.is_checked():
                await agreement.check()
            await self.page.click(self.selector("login_button"))
            await self._wait_for_login_result()
        except (RpaBusinessError, RpaRetryableError):
            raise
        except Exception as exc:
            await self._redact_login_fields()
            raise RpaRetryableError(
                "SRM_LOGIN_FAILED",
                "Supplier portal login failed",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Supplier portal login completed",
            payload={"stepId": step_id},
        )

    async def _wait_for_login_result(self):
        success = self.page.locator(self.selector("login_success"))
        error = self.page.locator(self.selector("login_error"))
        for _ in range(50):
            if await success.is_visible():
                return
            if await error.is_visible():
                await self._redact_login_fields()
                raise RpaBusinessError(
                    "SRM_LOGIN_FAILED",
                    "Supplier portal login failed",
                )
            await self.page.wait_for_timeout(200)
        await self._redact_login_fields()
        raise RpaRetryableError(
            "SRM_LOGIN_TIMEOUT",
            "Supplier portal login did not complete in time",
        )

    async def _redact_login_fields(self):
        for name in ("username", "password", "captcha"):
            try:
                await self.page.fill(self.selector(name), "")
            except Exception:
                continue

    async def open_order_detail(self, po_no):
        step_id = "srm.search_po"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Searching for customer purchase order",
            payload={"stepId": step_id, "stepType": step_id, "poNo": po_no},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        try:
            await self.page.goto(f"{portal_root}/#/supplier/orders", wait_until="domcontentloaded")
            await self.page.locator(self.selector("order_page")).wait_for(state="visible", timeout=10000)
            await self.page.fill(self.selector("po_number"), po_no)
            await self.page.click(self.selector("search_button"))
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_SEARCH_UNAVAILABLE",
                "Customer purchase order search could not be completed",
            ) from exc
        row = self.page.locator(self.selector("order_row", po_no=po_no))
        try:
            await row.wait_for(state="visible", timeout=10000)
        except Exception as exc:
            raise RpaBusinessError(
                "BUSINESS_NOT_FOUND",
                "Customer purchase order was not found",
            ) from exc
        try:
            await self.page.click(self.selector("order_detail", po_no=po_no))
            await self.page.locator(self.selector("detail_page")).wait_for(state="visible", timeout=15000)
            await self.page.locator(self.selector("detail_po_number", po_no=po_no)).wait_for(
                state="visible", timeout=15000
            )
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DETAIL_UNAVAILABLE",
                "Customer purchase order detail could not be verified",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Customer purchase order detail opened",
            payload={"stepId": step_id, "poNo": po_no},
        )

    async def reply_status(self):
        try:
            status = self.page.locator(self.selector("reply_status"))
            await status.wait_for(state="visible", timeout=10000)
            value = _clean(await status.inner_text())
            if not value:
                raise ValueError("reply status is empty")
            return value
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_REPLY_STATUS_UNAVAILABLE",
                "Order reply status could not be read",
            ) from exc


async def run(ctx):
    """只读探测 SRM 订单回复状态；绝不点击签章。"""
    po_no = validate_input(ctx.input if isinstance(ctx.input, Mapping) else {})
    if not ctx.portal_url:
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")

    await ctx.log.info("Starting SRM reply-status check Flow", {"poNo": po_no})
    adapter = SupplierPortalReplyStatusAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)

    step_id = "srm.check_reply_status"
    await ctx.events.emit(
        "STEP_STARTED",
        message="Reading order reply status",
        payload={"stepId": step_id, "stepType": step_id, "poNo": po_no},
    )
    try:
        reply_status = await adapter.reply_status()
    except (RpaBusinessError, RpaHumanRequiredError, RpaRetryableError) as error:
        await _safe_emit(
            ctx,
            "STEP_WAITING_HUMAN" if isinstance(error, RpaHumanRequiredError) else "STEP_FAILED",
            level="WARNING" if isinstance(error, RpaHumanRequiredError) else "ERROR",
            message="Order reply status could not be confirmed",
            payload={"stepId": step_id, "errorCode": error.code, "poNo": po_no},
        )
        raise

    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Order reply status read",
        payload={"stepId": step_id, "poNo": po_no, "replyStatus": reply_status},
    )
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "poNo": po_no,
        "replyStatus": reply_status,
    }
