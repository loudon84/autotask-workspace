import asyncio
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
SIGN_SUCCESS_TEXT = "签章成功"
SIGNED_REPLY_STATUS = "已回签"
PENDING_REPLY_STATUS = "待回签"
OUTPUT_SCHEMA_VERSION = "SRM_SIGN_ORDER_OUTPUT_V1"

COLLECT_LINE_DATES_JS = r"""(tableSelector) => {
  const table = document.querySelector(tableSelector);
  if (!table) return [];
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const body = table.querySelector(':scope > .el-table__body-wrapper tbody');
  if (!body) return [];
  const result = [];
  for (const row of body.querySelectorAll(':scope > tr')) {
    const cells = row.querySelectorAll(':scope > td');
    const lineNo = clean(cells[0]?.textContent);
    const materialNo = clean(cells[1]?.textContent);
    const dateInput = row.querySelector(
      '[data-rpa^=pend-order-detail-expected-date-] input'
    );
    const currentExpectedDate = dateInput ? clean(dateInput.value) : '';
    if (!lineNo || !materialNo) continue;
    result.push({ lineNo, materialNo, currentExpectedDate });
  }
  return result;
}"""


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
    # TEMP_E2E_ONLY: 联调结束后删除 backfill 解析。
    backfill_lines = []
    if bool(value.get("temp_e2e_backfill_dates")):
        raw_lines = value.get("order_lines")
        if not isinstance(raw_lines, list) or not raw_lines:
            raise RpaBusinessError(
                "FLOW_INPUT_INVALID",
                "temp_e2e_backfill_dates requires non-empty order_lines",
            )
        for raw in raw_lines:
            if not isinstance(raw, Mapping):
                continue
            line_no = _clean(raw.get("line_number") or raw.get("lineNo"))
            expected_date = _clean(
                raw.get("expected_delivery_date") or raw.get("expectedDeliveryDate")
            )
            if not line_no or not expected_date:
                continue
            backfill_lines.append(
                {"lineNo": line_no, "expectedDeliveryDate": expected_date}
            )
        if not backfill_lines:
            raise RpaBusinessError(
                "FLOW_INPUT_INVALID",
                "temp_e2e_backfill_dates order_lines has no usable dates",
            )
    return po_no, backfill_lines


def ensure_all_dates_filled(raw_lines):
    """签章前置校验：门户上每一行都必须已有预计交货日期。"""
    if not isinstance(raw_lines, list) or not raw_lines:
        raise RpaBusinessError(
            "ORDER_LINES_NOT_FOUND",
            "Customer purchase order does not contain order lines",
        )
    missing = []
    lines = []
    for raw in raw_lines:
        if not isinstance(raw, Mapping):
            raise RpaBusinessError(
                "ORDER_LINE_DATA_AMBIGUOUS",
                "Customer purchase order line data is invalid",
            )
        line_no = _clean(raw.get("lineNo"))
        current_date = _clean(raw.get("currentExpectedDate"))
        if not line_no:
            raise RpaBusinessError(
                "ORDER_LINE_DATA_AMBIGUOUS",
                "Customer purchase order line identity is missing",
            )
        if not current_date:
            missing.append(line_no)
        lines.append(
            {
                "lineNo": line_no,
                "materialNo": _clean(raw.get("materialNo")),
                "expectedDeliveryDate": current_date,
            }
        )
    if missing:
        raise RpaBusinessError(
            "ORDER_DATES_INCOMPLETE",
            "Some order lines have no expected delivery date on the portal",
            details={"missingLineNumbers": missing},
        )
    return lines


async def _safe_emit(ctx, event_type, *, level="INFO", message, payload=None):
    try:
        await ctx.events.emit(event_type, level=level, message=message, payload=payload)
    except Exception:
        return


async def _safe_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return


class SupplierPortalSignAdapter:
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
            await _safe_screenshot(self.ctx, "supplier-portal-captcha-unknown", step_id)
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
            await self.page.locator(self.selector("lines_table")).wait_for(state="visible", timeout=15000)
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

    async def collect_order_lines(self):
        try:
            result = await self.page.evaluate(COLLECT_LINE_DATES_JS, self.selector("lines_table"))
            if not isinstance(result, list) or not result:
                raise RpaBusinessError(
                    "ORDER_LINES_NOT_FOUND",
                    "Customer purchase order does not contain order lines",
                )
            return result
        except RpaBusinessError:
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_LINES_UNAVAILABLE",
                "Customer purchase order lines could not be read",
            ) from exc

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

    async def ensure_signable(self):
        try:
            sign_button = self.page.locator(self.selector("sign")).first
            if not await sign_button.is_visible() or not await sign_button.is_enabled():
                raise RpaBusinessError(
                    "ORDER_NOT_EDITABLE",
                    "Customer purchase order cannot be signed",
                )
        except RpaBusinessError:
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_EDITABILITY_UNAVAILABLE",
                "Order sign action state could not be verified",
            ) from exc

    async def _pick_date_input(self, line_no):
        primary = self.page.locator(self.selector("expected_date", line_no=line_no)).first
        try:
            if await primary.count() > 0 and await primary.is_visible():
                return primary
        except Exception:
            pass
        return self.page.locator(self.selector("expected_date_fallback", line_no=line_no)).first

    async def temp_e2e_backfill_dates(self, backfill_lines):
        """TEMP_E2E_ONLY: 按 AutoTask 日期写入页面输入框（不点保存），供随后签章。联调后删除。"""
        for item in backfill_lines:
            line_no = item["lineNo"]
            expected_date = item["expectedDeliveryDate"]
            field = await self._pick_date_input(line_no)
            await field.wait_for(state="visible", timeout=5000)
            if not await field.is_enabled():
                raise RpaBusinessError(
                    "ORDER_NOT_EDITABLE",
                    "The expected delivery date field is not editable",
                    details={"lineNo": line_no},
                )
            await field.click()
            await field.fill("")
            await field.type(expected_date, delay=20)
            await field.press("Enter")
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
            await self.page.wait_for_timeout(150)
            actual = _clean(await field.input_value())
            if actual != expected_date:
                raise RpaRetryableError(
                    "ORDER_DATE_FILL_FAILED",
                    "TEMP E2E backfill did not retain the AutoTask delivery date",
                    details={"lineNo": line_no, "actual": actual},
                )

    async def _wait_for_action_result(self):
        success = self.page.locator(self.selector("sign_success"))
        error = self.page.locator(self.selector("sign_error"))
        for _ in range(75):
            if await success.is_visible():
                message = _clean(await success.inner_text())
                if SIGN_SUCCESS_TEXT in message:
                    return message[:500]
            if await error.is_visible():
                message = _clean(await error.inner_text())[:500]
                raise RpaBusinessError(
                    "ORDER_SIGN_REJECTED",
                    message or "Supplier portal rejected the sign action",
                )
            await self.page.wait_for_timeout(200)
        raise RpaHumanRequiredError(
            "ORDER_SIGN_OUTCOME_UNKNOWN",
            "Supplier portal sign result requires manual verification",
        )

    async def sign_and_verify(self, po_no):
        try:
            await self.page.locator(self.selector("sign")).first.click(timeout=10000)
            success_message = await self._wait_for_action_result()
        except asyncio.CancelledError:
            raise RpaHumanRequiredError(
                "ORDER_SIGN_OUTCOME_UNKNOWN",
                "Order sign result requires manual verification",
            ) from None
        except (RpaBusinessError, RpaHumanRequiredError):
            raise
        except Exception as exc:
            raise RpaHumanRequiredError(
                "ORDER_SIGN_OUTCOME_UNKNOWN",
                "Order sign result requires manual verification",
            ) from exc

        try:
            await self.page.reload(wait_until="domcontentloaded")
            await self.page.locator(self.selector("detail_po_number", po_no=po_no)).wait_for(
                state="visible", timeout=15000
            )
            status = await self.reply_status()
            if status not in {SIGNED_REPLY_STATUS, PENDING_REPLY_STATUS}:
                raise RpaHumanRequiredError(
                    "ORDER_SIGN_STATUS_UNCONFIRMED",
                    "Order reply status was not confirmed after sign",
                    details={"replyStatus": status},
                )
            return success_message, status
        except asyncio.CancelledError:
            raise RpaHumanRequiredError(
                "ORDER_SIGN_STATUS_UNCONFIRMED",
                "Signed order status requires manual verification",
            ) from None
        except RpaHumanRequiredError:
            raise
        except Exception as exc:
            raise RpaHumanRequiredError(
                "ORDER_SIGN_STATUS_UNCONFIRMED",
                "Signed order status requires manual verification",
            ) from exc


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError(
            "PORTAL_URL_MISSING",
            "Supplier portal URL is unavailable",
        )
    po_no, backfill_lines = validate_input(getattr(ctx, "input", None))
    await ctx.log.info(
        "Starting supplier portal sign-only Flow",
        {
            "poNo": po_no,
            "tempE2eBackfill": bool(backfill_lines),
            "backfillCount": len(backfill_lines),
        },
    )

    adapter = SupplierPortalSignAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)

    reply_status = await adapter.reply_status()
    if reply_status in {SIGNED_REPLY_STATUS, PENDING_REPLY_STATUS}:
        portal_lines = await adapter.collect_order_lines()
        await _safe_emit(
            ctx,
            "STEP_SUCCEEDED",
            message="Order already signed or pending counter-signature",
            payload={"stepId": "srm.idempotency", "poNo": po_no, "replyStatus": reply_status},
        )
        return {
            "schemaVersion": OUTPUT_SCHEMA_VERSION,
            "poNo": po_no,
            "signed": True,
            "replyStatus": reply_status,
            "idempotent": True,
            "lineCount": len(portal_lines),
            "tempE2eBackfill": False,
        }

    # TEMP_E2E_ONLY: 门户不落库时，签章前把 AutoTask 交期填进页面。联调后删除本段。
    if backfill_lines:
        await ctx.events.emit(
            "STEP_STARTED",
            message="TEMP E2E: backfilling AutoTask delivery dates before sign",
            payload={
                "stepId": "srm.temp_e2e_backfill_dates",
                "stepType": "srm.temp_e2e_backfill_dates",
                "poNo": po_no,
                "lineCount": len(backfill_lines),
            },
        )
        await adapter.temp_e2e_backfill_dates(backfill_lines)
        await _safe_emit(
            ctx,
            "STEP_SUCCEEDED",
            message="TEMP E2E: AutoTask delivery dates backfilled into portal form",
            payload={"stepId": "srm.temp_e2e_backfill_dates", "poNo": po_no},
        )
        lines = [
            {
                "lineNo": item["lineNo"],
                "materialNo": "",
                "expectedDeliveryDate": item["expectedDeliveryDate"],
            }
            for item in backfill_lines
        ]
    else:
        lines = ensure_all_dates_filled(await adapter.collect_order_lines())

    await adapter.ensure_signable()
    step_id = "srm.sign_order"
    await ctx.events.emit(
        "STEP_STARTED",
        message="Signing customer purchase order",
        payload={"stepId": step_id, "stepType": step_id, "poNo": po_no, "lineCount": len(lines)},
    )
    try:
        _message, reply_status = await adapter.sign_and_verify(po_no)
    except (RpaBusinessError, RpaHumanRequiredError) as error:
        await _safe_screenshot(ctx, "supplier-portal-sign-failed", step_id)
        await _safe_emit(
            ctx,
            "STEP_WAITING_HUMAN" if isinstance(error, RpaHumanRequiredError) else "STEP_FAILED",
            level="WARNING" if isinstance(error, RpaHumanRequiredError) else "ERROR",
            message="Order sign failed or requires manual verification",
            payload={"stepId": step_id, "errorCode": error.code, "poNo": po_no},
        )
        raise
    await _safe_screenshot(ctx, "supplier-portal-order-signed", step_id)
    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Customer purchase order signed",
        payload={"stepId": step_id, "poNo": po_no, "replyStatus": reply_status},
    )
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "poNo": po_no,
        "signed": True,
        "replyStatus": reply_status,
        "idempotent": False,
        "lineCount": len(lines),
        "tempE2eBackfill": bool(backfill_lines),
    }
