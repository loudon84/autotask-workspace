import asyncio
import re
from collections.abc import Mapping
from datetime import date

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
LINE_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MATERIAL_NUMBER_PATTERN = re.compile(r"^[^\s\r\n\t][^\r\n\t]{0,239}$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SIGN_SUCCESS_TEXT = "签章成功"
SIGNED_REPLY_STATUS = "已回签"
OUTPUT_SCHEMA_VERSION = "ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1"


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_captcha_code(image_src):
    if not isinstance(image_src, str) or not image_src.strip():
        return None
    clean_src = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean_src.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


def _mapping_error(message, *, details=None):
    raise RpaBusinessError(
        "DELIVERY_DATE_MAPPING_INVALID",
        message,
        details=details,
    )


def validate_input(raw_input):
    value = raw_input if isinstance(raw_input, Mapping) else {}
    po_no = _clean(value.get("po_no")).upper()
    if not PO_NUMBER_PATTERN.fullmatch(po_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Customer purchase order number is missing or invalid",
        )

    raw_lines = value.get("order_lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        _mapping_error("order_lines must be a non-empty array")

    lines = []
    seen_line_numbers = set()
    for index, raw_line in enumerate(raw_lines):
        if not isinstance(raw_line, Mapping):
            _mapping_error(
                "Every order_lines item must be an object",
                details={"index": index},
            )
        line_no = _clean(raw_line.get("line_number"))
        material_no = _clean(raw_line.get("material_number"))
        expected_date = _clean(raw_line.get("expected_delivery_date"))

        if not LINE_NUMBER_PATTERN.fullmatch(line_no):
            _mapping_error(
                "An order line number is missing or invalid",
                details={"index": index},
            )
        if line_no in seen_line_numbers:
            _mapping_error(
                "order_lines contains a duplicate line number",
                details={"lineNo": line_no},
            )
        seen_line_numbers.add(line_no)

        if not MATERIAL_NUMBER_PATTERN.fullmatch(material_no):
            _mapping_error(
                "An order line material number is missing or invalid",
                details={"lineNo": line_no},
            )
        if not ISO_DATE_PATTERN.fullmatch(expected_date):
            _mapping_error(
                "Expected delivery date must use YYYY-MM-DD",
                details={"lineNo": line_no},
            )
        try:
            parsed_date = date.fromisoformat(expected_date)
        except ValueError as exc:
            raise RpaBusinessError(
                "DELIVERY_DATE_MAPPING_INVALID",
                "Expected delivery date is not a valid calendar date",
                details={"lineNo": line_no},
            ) from exc
        if parsed_date.isoformat() != expected_date:
            _mapping_error(
                "Expected delivery date is not canonical ISO format",
                details={"lineNo": line_no},
            )

        lines.append(
            {
                "lineNo": line_no,
                "materialNo": material_no,
                "expectedDeliveryDate": expected_date,
            }
        )
    return po_no, lines


def reconcile_order_lines(raw_lines, requested_lines):
    if not isinstance(raw_lines, list) or not raw_lines:
        raise RpaBusinessError(
            "ORDER_LINES_NOT_FOUND",
            "Customer purchase order does not contain order lines",
        )

    page_lines = []
    page_by_line = {}
    for raw_line in raw_lines:
        if not isinstance(raw_line, Mapping):
            raise RpaBusinessError(
                "ORDER_LINE_DATA_AMBIGUOUS",
                "Customer purchase order line data is invalid",
            )
        line_no = _clean(raw_line.get("lineNo"))
        material_no = _clean(raw_line.get("materialNo"))
        current_date = _clean(raw_line.get("currentExpectedDate"))
        if not LINE_NUMBER_PATTERN.fullmatch(
            line_no
        ) or not MATERIAL_NUMBER_PATTERN.fullmatch(material_no):
            raise RpaBusinessError(
                "ORDER_LINE_DATA_AMBIGUOUS",
                "Customer purchase order line identity is missing or invalid",
            )
        if line_no in page_by_line:
            raise RpaBusinessError(
                "ORDER_LINE_DATA_AMBIGUOUS",
                "Customer purchase order contains duplicate line numbers",
                details={"lineNo": line_no},
            )
        page_line = {
            "lineNo": line_no,
            "materialNo": material_no,
            "currentExpectedDate": current_date,
        }
        page_lines.append(page_line)
        page_by_line[line_no] = page_line

    requested_by_line = {line["lineNo"]: line for line in requested_lines}
    missing = sorted(set(page_by_line) - set(requested_by_line))
    extra = sorted(set(requested_by_line) - set(page_by_line))
    if missing or extra:
        raise RpaBusinessError(
            "DELIVERY_DATE_LINE_MISMATCH",
            "order_lines must exactly cover all portal order lines",
            details={"missingLineNumbers": missing, "extraLineNumbers": extra},
        )

    mismatches = []
    for line_no, page_line in page_by_line.items():
        requested = requested_by_line[line_no]
        if page_line["materialNo"] != requested["materialNo"]:
            mismatches.append(
                {
                    "lineNo": line_no,
                    "expectedMaterialNo": requested["materialNo"],
                    "actualMaterialNo": page_line["materialNo"],
                }
            )
    if mismatches:
        raise RpaBusinessError(
            "DELIVERY_DATE_LINE_MISMATCH",
            "An order line material number does not match the portal",
            details={"materialMismatches": mismatches},
        )

    return [
        {**requested_by_line[page_line["lineNo"]], **page_line}
        for page_line in page_lines
    ]


def _dates_match(lines):
    return all(
        line["currentExpectedDate"] == line["expectedDeliveryDate"] for line in lines
    )


async def _safe_emit(ctx, event_type, *, level="INFO", message, payload=None):
    try:
        await ctx.events.emit(
            event_type,
            level=level,
            message=message,
            payload=payload,
        )
    except Exception:
        return


async def _safe_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return


class SupplierPortalDeliveryDateAdapter:
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
        credentials = (
            self.ctx.credentials if isinstance(self.ctx.credentials, Mapping) else {}
        )
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
        await self.page.goto(self.ctx.portal_url, wait_until="domcontentloaded")
        captcha = self.page.locator(self.selector("captcha_image"))
        try:
            await captcha.wait_for(state="visible", timeout=10000)
            code = resolve_captcha_code(await captcha.get_attribute("src"))
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_LOGIN_PAGE_UNAVAILABLE",
                "Supplier portal login page could not be loaded",
            ) from exc
        if code is None:
            await self._redact_login_fields()
            await _safe_screenshot(
                self.ctx,
                "supplier-portal-captcha-unknown",
                step_id,
            )
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
            await self.page.goto(
                f"{portal_root}/#/supplier/orders",
                wait_until="domcontentloaded",
            )
            await self.page.locator(self.selector("order_page")).wait_for(
                state="visible",
                timeout=10000,
            )
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
            await self.page.locator(self.selector("detail_page")).wait_for(
                state="visible",
                timeout=15000,
            )
            await self.page.locator(
                self.selector("detail_po_number", po_no=po_no)
            ).wait_for(state="visible", timeout=15000)
            await self.page.locator(self.selector("lines_table")).wait_for(
                state="visible",
                timeout=15000,
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

    async def collect_order_lines(self):
        try:
            result = await self.page.evaluate(
                r"""(tableSelector) => {
                  const table = document.querySelector(tableSelector);
                  if (!table) return [];
                  const clean = (value) =>
                    String(value || '').replace(/\s+/g, ' ').trim();
                  const body = table.querySelector(
                    ':scope > .el-table__body-wrapper tbody'
                  );
                  if (!body) return [];
                  const headers = [
                    ...table.querySelectorAll(
                      ':scope > .el-table__header-wrapper th'
                    ),
                  ].map((header) => clean(header.textContent));
                  const expectedDateIndex = headers.indexOf('预计交货日期');
                  const result = [];
                  for (const row of body.querySelectorAll(':scope > tr')) {
                    const cells = row.querySelectorAll(':scope > td');
                    const lineNo = clean(cells[0]?.textContent);
                    const materialNo = clean(cells[1]?.textContent);
                    const dateInput = row.querySelector(
                      '[data-rpa^=pend-order-detail-expected-date-] input'
                    );
                    const currentExpectedDate = dateInput
                      ? clean(dateInput.value)
                      : expectedDateIndex >= 0
                        ? clean(cells[expectedDateIndex]?.textContent)
                        : '';
                    if (!lineNo || !materialNo) continue;
                    result.push({
                      lineNo,
                      materialNo,
                      currentExpectedDate,
                    });
                  }
                  return result;
                }""",
                self.selector("lines_table"),
            )
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

    def date_input(self, line_no):
        return self.page.locator(self.selector("expected_date", line_no=line_no))

    async def ensure_editable(self, lines):
        try:
            sign_button = self.page.locator(self.selector("sign"))
            if not await sign_button.is_visible() or not await sign_button.is_enabled():
                raise RpaBusinessError(
                    "ORDER_NOT_EDITABLE",
                    "Customer purchase order cannot be signed",
                )
            for line in lines:
                field = self.date_input(line["lineNo"])
                await field.wait_for(state="visible", timeout=5000)
                if not await field.is_enabled():
                    raise RpaBusinessError(
                        "ORDER_NOT_EDITABLE",
                        "An expected delivery date field is not editable",
                        details={"lineNo": line["lineNo"]},
                    )
        except RpaBusinessError:
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_EDITABILITY_UNAVAILABLE",
                "Order editability could not be verified",
            ) from exc

    async def ensure_sign_not_executable(self):
        try:
            sign_button = self.page.locator(self.selector("sign"))
            if not await sign_button.is_visible():
                return
            if await sign_button.is_enabled():
                raise RpaHumanRequiredError(
                    "ORDER_SIGN_STATUS_UNCONFIRMED",
                    "Signed order still exposes an executable sign action",
                )
        except RpaHumanRequiredError:
            raise
        except Exception as exc:
            raise RpaHumanRequiredError(
                "ORDER_SIGN_STATUS_UNCONFIRMED",
                "Signed order action state could not be verified",
            ) from exc

    async def fill_and_verify(self, lines):
        try:
            for line in lines:
                field = self.date_input(line["lineNo"])
                await field.fill(line["expectedDeliveryDate"])
                await field.press("Tab")
            for line in lines:
                actual = _clean(await self.date_input(line["lineNo"]).input_value())
                if actual != line["expectedDeliveryDate"]:
                    raise RpaRetryableError(
                        "ORDER_DATE_FILL_FAILED",
                        "An expected delivery date did not retain its input value",
                        details={"lineNo": line["lineNo"]},
                    )
        except RpaRetryableError:
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DATE_FILL_FAILED",
                "Expected delivery dates could not be filled",
            ) from exc

    async def wait_for_detail_stable(
        self,
        expected_lines,
        *,
        expected_status=None,
    ):
        try:
            await self.page.locator(self.selector("loading_mask")).wait_for(
                state="hidden",
                timeout=15000,
            )
            rendered = None
            for _ in range(50):
                try:
                    rendered = reconcile_order_lines(
                        await self.collect_order_lines(),
                        expected_lines,
                    )
                    status_matches = (
                        expected_status is None
                        or await self.reply_status() == expected_status
                    )
                    if _dates_match(rendered) and status_matches:
                        break
                except (RpaBusinessError, RpaRetryableError):
                    pass
                await self.page.wait_for_timeout(200)
            else:
                raise ValueError("detail rows or dates did not stabilize")

            await self.page.evaluate(
                """async () => {
                  if (document.fonts && document.fonts.ready) {
                    await document.fonts.ready;
                  }
                  const visible = (element) => {
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none' &&
                      style.visibility !== 'hidden' &&
                      rect.width > 0 && rect.height > 0;
                  };
                  const images = [...document.images].filter(visible);
                  await Promise.all(images.map((image) => {
                    if (image.complete) return Promise.resolve();
                    return new Promise((resolve, reject) => {
                      const timer = setTimeout(
                        () => reject(new Error('visible image timeout')),
                        10000
                      );
                      const done = () => {
                        clearTimeout(timer);
                        resolve();
                      };
                      image.addEventListener('load', done, {once: true});
                      image.addEventListener('error', done, {once: true});
                    });
                  }));
                }"""
            )

            previous = None
            stable_pairs = 0
            for _ in range(30):
                layout = await self.page.evaluate(
                    """() => {
                      const detail = document.querySelector(
                        '[data-rpa=order-detail-page], ' +
                        '[data-rpa=pend-order-detail-page]'
                      );
                      if (!detail) return null;
                      const rect = detail.getBoundingClientRect();
                      return {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        scrollWidth: detail.scrollWidth,
                        scrollHeight: detail.scrollHeight,
                        bodyHeight: document.body.scrollHeight,
                      };
                    }"""
                )
                if layout is not None and layout == previous:
                    stable_pairs += 1
                    if stable_pairs >= 1:
                        break
                else:
                    stable_pairs = 0
                previous = layout
                await self.page.wait_for_timeout(100)
            else:
                raise ValueError("detail layout did not stabilize")
            await self.page.wait_for_timeout(300)
            return rendered
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DETAIL_NOT_STABLE",
                "Order detail did not become stable for evidence capture",
            ) from exc

    async def capture_stable_screenshot(
        self,
        name,
        step_id,
        expected_lines,
        *,
        expected_status=None,
    ):
        await self.wait_for_detail_stable(
            expected_lines,
            expected_status=expected_status,
        )
        await self.ctx.artifacts.screenshot(name, step_id=step_id)

    async def capture_failure_screenshot(self, name, step_id):
        await _safe_screenshot(self.ctx, name, step_id)

    async def _wait_for_action_result(
        self,
        *,
        success_selector,
        error_selector,
        success_text,
        rejected_code,
        unknown_code,
    ):
        success = self.page.locator(self.selector(success_selector))
        error = self.page.locator(self.selector(error_selector))
        for _ in range(75):
            if await success.is_visible():
                message = _clean(await success.inner_text())
                if success_text in message:
                    return message[:500]
            if await error.is_visible():
                message = _clean(await error.inner_text())[:500]
                raise RpaBusinessError(
                    rejected_code,
                    message or "Supplier portal rejected the requested action",
                )
            await self.page.wait_for_timeout(200)
        raise RpaHumanRequiredError(
            unknown_code,
            "Supplier portal action result requires manual verification",
        )

    async def sign_and_verify(self, po_no, lines):
        try:
            await self.page.locator(self.selector("sign")).click(timeout=10000)
            success_message = await self._wait_for_action_result(
                success_selector="sign_success",
                error_selector="sign_error",
                success_text=SIGN_SUCCESS_TEXT,
                rejected_code="ORDER_SIGN_REJECTED",
                unknown_code="ORDER_SIGN_OUTCOME_UNKNOWN",
            )
            if SIGNED_REPLY_STATUS not in success_message:
                raise RpaHumanRequiredError(
                    "ORDER_SIGN_OUTCOME_UNKNOWN",
                    "Sign response did not confirm the signed reply status",
                )
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
            await self.page.locator(
                self.selector("detail_po_number", po_no=po_no)
            ).wait_for(state="visible", timeout=15000)
            status = await self.reply_status()
            if status != SIGNED_REPLY_STATUS:
                raise RpaHumanRequiredError(
                    "ORDER_SIGN_STATUS_UNCONFIRMED",
                    "Order reply status was not confirmed as signed",
                    details={"replyStatus": status},
                )
            await self.ensure_sign_not_executable()
            persisted = reconcile_order_lines(
                await self.collect_order_lines(),
                lines,
            )
            if not _dates_match(persisted):
                raise RpaHumanRequiredError(
                    "ORDER_SIGN_STATUS_UNCONFIRMED",
                    "Signed order dates do not match the requested values",
                )
            return success_message, status, persisted
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


def _success_result(po_no, lines):
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "poNo": po_no,
        "lineCount": len(lines),
        "saved": True,
        "signed": True,
        "replyStatus": SIGNED_REPLY_STATUS,
        "lines": [
            {
                "lineNo": line["lineNo"],
                "materialNo": line["materialNo"],
                "expectedDeliveryDate": line["expectedDeliveryDate"],
            }
            for line in lines
        ],
    }


async def _post_action_failure(
    ctx,
    adapter,
    *,
    step_id,
    screenshot_name,
    error,
    po_no,
):
    await adapter.capture_failure_screenshot(screenshot_name, step_id)
    waiting_human = isinstance(error, RpaHumanRequiredError)
    await _safe_emit(
        ctx,
        "STEP_WAITING_HUMAN" if waiting_human else "STEP_FAILED",
        level="WARNING" if waiting_human else "ERROR",
        message="Portal write requires manual verification"
        if waiting_human
        else "Portal write was rejected",
        payload={
            "stepId": step_id,
            "errorCode": error.code,
            "poNo": po_no,
        },
    )


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError(
            "PORTAL_URL_MISSING",
            "Supplier portal URL is unavailable",
        )
    po_no, requested_lines = validate_input(getattr(ctx, "input", None))
    await ctx.log.info(
        "Starting supplier portal delivery-date save and sign Flow",
        {"poNo": po_no, "lineCount": len(requested_lines)},
    )

    adapter = SupplierPortalDeliveryDateAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)
    lines = reconcile_order_lines(
        await adapter.collect_order_lines(),
        requested_lines,
    )
    reply_status = await adapter.reply_status()

    if reply_status == SIGNED_REPLY_STATUS:
        if not _dates_match(lines):
            error = RpaHumanRequiredError(
                "ORDER_ALREADY_CONFIRMED_CONFLICT",
                "Order is already signed with different expected delivery dates",
                details={
                    "lineNumbers": [
                        line["lineNo"]
                        for line in lines
                        if line["currentExpectedDate"] != line["expectedDeliveryDate"]
                    ]
                },
            )
            await adapter.capture_failure_screenshot(
                "supplier-portal-delivery-dates-already-signed-conflict",
                "srm.idempotency",
            )
            await _safe_emit(
                ctx,
                "STEP_WAITING_HUMAN",
                level="WARNING",
                message="Already signed order conflicts with requested dates",
                payload={
                    "stepId": "srm.idempotency",
                    "errorCode": error.code,
                    "poNo": po_no,
                },
            )
            raise error
        await adapter.ensure_sign_not_executable()
        await adapter.capture_stable_screenshot(
            "supplier-portal-delivery-dates-signed",
            "srm.idempotency",
            lines,
            expected_status=SIGNED_REPLY_STATUS,
        )
        await _safe_emit(
            ctx,
            "STEP_SUCCEEDED",
            message="Already signed order matches requested dates",
            payload={
                "stepId": "srm.idempotency",
                "poNo": po_no,
                "lineCount": len(lines),
            },
        )
        return _success_result(po_no, lines)

    await adapter.ensure_editable(lines)
    await ctx.events.emit(
        "STEP_STARTED",
        message="Filling expected delivery dates by order line",
        payload={
            "stepId": "srm.fill_delivery_dates",
            "stepType": "srm.fill_delivery_dates",
            "poNo": po_no,
            "lineCount": len(lines),
        },
    )
    await adapter.fill_and_verify(lines)
    await adapter.capture_stable_screenshot(
        "supplier-portal-delivery-dates-before-sign",
        "srm.fill_delivery_dates",
        lines,
    )
    await ctx.events.emit(
        "STEP_SUCCEEDED",
        message="Expected delivery dates filled and stable before sign",
        payload={
            "stepId": "srm.fill_delivery_dates",
            "poNo": po_no,
            "lineCount": len(lines),
        },
    )

    await _safe_emit(
        ctx,
        "STEP_STARTED",
        message="Signing customer purchase order",
        payload={
            "stepId": "srm.sign_order",
            "stepType": "srm.sign_order",
            "poNo": po_no,
            "lineCount": len(lines),
        },
    )
    try:
        _sign_message, reply_status, lines = await adapter.sign_and_verify(
            po_no,
            lines,
        )
        try:
            await adapter.capture_stable_screenshot(
                "supplier-portal-delivery-dates-signed",
                "srm.sign_order",
                lines,
                expected_status=SIGNED_REPLY_STATUS,
            )
        except Exception as exc:
            raise RpaHumanRequiredError(
                "ORDER_SIGN_STATUS_UNCONFIRMED",
                "Signed page could not be stabilized for verification evidence",
            ) from exc
    except (RpaBusinessError, RpaHumanRequiredError) as error:
        await _post_action_failure(
            ctx,
            adapter,
            step_id="srm.sign_order",
            screenshot_name="supplier-portal-delivery-dates-sign-failed",
            error=error,
            po_no=po_no,
        )
        raise
    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Customer purchase order signed and verified",
        payload={
            "stepId": "srm.sign_order",
            "poNo": po_no,
            "lineCount": len(lines),
            "replyStatus": reply_status,
        },
    )
    return _success_result(po_no, lines)
