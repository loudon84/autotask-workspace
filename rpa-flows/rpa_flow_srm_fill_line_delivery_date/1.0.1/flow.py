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
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SIGNED_REPLY_STATUS = "已回签"
OUTPUT_SCHEMA_VERSION = "SRM_FILL_LINE_DATE_OUTPUT_V1"

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
    line_no = _clean(value.get("line_number"))
    if not LINE_NUMBER_PATTERN.fullmatch(line_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Order line number is missing or invalid",
        )
    expected_date = _clean(value.get("expected_delivery_date"))
    if not ISO_DATE_PATTERN.fullmatch(expected_date):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Expected delivery date must use YYYY-MM-DD",
        )
    try:
        parsed = date.fromisoformat(expected_date)
    except ValueError as exc:
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Expected delivery date is not a valid calendar date",
        ) from exc
    if parsed.isoformat() != expected_date:
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Expected delivery date is not canonical ISO format",
        )
    return po_no, line_no, expected_date


def find_line(raw_lines, line_no):
    """从门户行数据中定位目标行；不存在或重复均为业务错误。"""
    if not isinstance(raw_lines, list) or not raw_lines:
        raise RpaBusinessError(
            "ORDER_LINES_NOT_FOUND",
            "Customer purchase order does not contain order lines",
        )
    matches = []
    for raw in raw_lines:
        if not isinstance(raw, Mapping):
            continue
        if _clean(raw.get("lineNo")) == line_no:
            matches.append(raw)
    if not matches:
        raise RpaBusinessError(
            "ORDER_LINE_NOT_FOUND",
            "Target order line was not found on the portal",
            details={"lineNo": line_no},
        )
    if len(matches) > 1:
        raise RpaBusinessError(
            "ORDER_LINE_DATA_AMBIGUOUS",
            "Target order line is ambiguous on the portal",
            details={"lineNo": line_no},
        )
    return matches[0]


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


class SupplierPortalFillLineAdapter:
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

    def date_input(self, line_no):
        # Element UI 固定列会复制控件；优先固定右列，并只取第一个匹配，避免 strict mode。
        return self.page.locator(self.selector("expected_date", line_no=line_no)).first

    async def fill_and_save_line(self, line_no, expected_date):
        field = self.date_input(line_no)
        try:
            await field.wait_for(state="visible", timeout=5000)
            if not await field.is_enabled():
                raise RpaBusinessError(
                    "ORDER_NOT_EDITABLE",
                    "The expected delivery date field is not editable",
                    details={"lineNo": line_no},
                )
            await field.click()
            await field.fill(expected_date)
            await field.press("Enter")
            actual = _clean(await field.input_value())
            if actual != expected_date:
                raise RpaRetryableError(
                    "ORDER_DATE_FILL_FAILED",
                    "The expected delivery date did not retain its input value",
                    details={"lineNo": line_no},
                )
        except (RpaBusinessError, RpaRetryableError):
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DATE_FILL_FAILED",
                "The expected delivery date could not be filled",
            ) from exc

        save_line = self.page.locator(self.selector("save_line", line_no=line_no)).first
        save_all = self.page.locator(self.selector("save_all")).first
        try:
            if await save_line.count() > 0 and await save_line.is_visible() and await save_line.is_enabled():
                await save_line.click(timeout=10000)
            elif await save_all.count() > 0 and await save_all.is_visible() and await save_all.is_enabled():
                await save_all.click(timeout=10000)
            else:
                raise RpaBusinessError(
                    "ORDER_NOT_EDITABLE",
                    "No enabled save action is available for the order line",
                    details={"lineNo": line_no},
                )
        except RpaBusinessError:
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_LINE_SAVE_FAILED",
                "The order line save action could not be executed",
            ) from exc

        success = self.page.locator(self.selector("save_success"))
        error = self.page.locator(self.selector("save_error"))
        for _ in range(50):
            if await success.is_visible():
                return
            if await error.is_visible():
                message = _clean(await error.inner_text())[:500]
                raise RpaBusinessError(
                    "ORDER_LINE_SAVE_REJECTED",
                    message or "Supplier portal rejected the line save",
                    details={"lineNo": line_no},
                )
            await self.page.wait_for_timeout(200)
        raise RpaHumanRequiredError(
            "ORDER_LINE_SAVE_OUTCOME_UNKNOWN",
            "Order line save result requires manual verification",
        )


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError(
            "PORTAL_URL_MISSING",
            "Supplier portal URL is unavailable",
        )
    po_no, line_no, expected_date = validate_input(getattr(ctx, "input", None))
    await ctx.log.info(
        "Starting supplier portal single-line delivery-date Flow",
        {"poNo": po_no, "lineNo": line_no, "expectedDeliveryDate": expected_date},
    )

    adapter = SupplierPortalFillLineAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)

    lines = await adapter.collect_order_lines()
    find_line(lines, line_no)
    reply_status = await adapter.reply_status()
    if reply_status == SIGNED_REPLY_STATUS:
        raise RpaBusinessError(
            "ORDER_ALREADY_SIGNED",
            "Order is already signed and cannot be edited",
            details={"poNo": po_no},
        )
    # 门户可能不落库；幂等以任务输入为准，不再要求 SRM 页面已显示该日期。

    step_id = "srm.fill_line_delivery_date"
    await ctx.events.emit(
        "STEP_STARTED",
        message="Filling and saving one expected delivery date",
        payload={
            "stepId": step_id,
            "stepType": step_id,
            "poNo": po_no,
            "lineNo": line_no,
        },
    )
    try:
        await adapter.fill_and_save_line(line_no, expected_date)
    except (RpaBusinessError, RpaHumanRequiredError) as error:
        await _safe_screenshot(ctx, "supplier-portal-fill-line-failed", step_id)
        await _safe_emit(
            ctx,
            "STEP_WAITING_HUMAN" if isinstance(error, RpaHumanRequiredError) else "STEP_FAILED",
            level="WARNING" if isinstance(error, RpaHumanRequiredError) else "ERROR",
            message="Order line save failed or requires manual verification",
            payload={"stepId": step_id, "errorCode": error.code, "poNo": po_no, "lineNo": line_no},
        )
        raise
    await _safe_screenshot(ctx, "supplier-portal-fill-line-saved", step_id)
    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Order line delivery date filled; AutoTask date is source of truth",
        payload={"stepId": step_id, "poNo": po_no, "lineNo": line_no},
    )
    # 演示门户可能只有成功提示、不写库。成功以 RPA 保存提示为准，日期以任务输入（AutoTask 已存）为准。
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "poNo": po_no,
        "lineNumber": line_no,
        "expectedDeliveryDate": expected_date,
        "saved": True,
        "idempotent": False,
        "portalPersisted": False,
    }
