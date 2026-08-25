"""SRM 生成对账单（正式门户）。

输入：dateStart / dateEnd（YYYY-MM-DD）, lines[{receiptNo,lineNo}]
操作：入库确认时间面板 → 对账状态=未提交 → 查询 → 勾选行 → 定位「生成对账单」
dryRun=true：按钮可见可点后截图，不 click。
dryRun=false：点击生成。
"""

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaRetryableError,
    install_write_guard,
    is_dry_run,
    login_official_srm,
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
OUTPUT_SCHEMA_VERSION = "SRM_STMT_GENERATE_OUTPUT_V1"
UNSUBMITTED_STATUS = "未提交"
RECONCILE_STATUS_LABEL = "对账状态"
START_TIME = "00:00:00"
END_TIME = "23:59:59"
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
READ_PICKER_MONTHS_JS = r"""() => {
  const panel = [...document.querySelectorAll('.el-date-range-picker')]
    .find((el) => el.offsetParent !== null);
  if (!panel) return { months: [] };
  const parse = (el) => {
    const text = ((el.querySelector('.el-date-range-picker__header') || el).innerText || '');
    const match = text.match(/(\d{4})\s*年\s*(\d{1,2})\s*月/);
    return match ? { year: Number(match[1]), month: Number(match[2]) } : null;
  };
  return {
    months: [...panel.querySelectorAll('.el-date-range-picker__content')]
      .map(parse)
      .filter(Boolean),
  };
}"""

CLICK_PICKER_DAY_JS = r"""({ year, month, day }) => {
  const panel = [...document.querySelectorAll('.el-date-range-picker')]
    .find((el) => el.offsetParent !== null);
  if (!panel) return 'no-panel';
  const parse = (el) => {
    const text = ((el.querySelector('.el-date-range-picker__header') || el).innerText || '');
    const match = text.match(/(\d{4})\s*年\s*(\d{1,2})\s*月/);
    return match ? [Number(match[1]), Number(match[2])] : [0, 0];
  };
  const content = [...panel.querySelectorAll('.el-date-range-picker__content')]
    .find((el) => {
      const [y, m] = parse(el);
      return y === year && m === month;
    });
  if (!content) return 'month-missing';
  const cell = [...content.querySelectorAll('td')].find((td) => {
    const cls = td.className || '';
    if (cls.includes('prev-month') || cls.includes('next-month') || cls.includes('disabled')) {
      return false;
    }
    return String(td.innerText || '').trim() === String(day);
  });
  if (!cell) return 'day-missing';
  cell.click();
  return 'ok';
}"""

SET_PICKER_RANGE_JS = r"""({ startDate, startTime, endDate, endTime }) => {
  const panel = [...document.querySelectorAll('.el-date-range-picker')]
    .find((el) => el.offsetParent !== null);
  if (!panel) return { ok: false, reason: 'no-panel' };
  let left = [];
  let right = [];
  const wraps = [...panel.querySelectorAll('.el-date-range-picker__editors-wrap')];
  if (wraps.length >= 2) {
    left = [...wraps[0].querySelectorAll('input')];
    right = [...wraps[1].querySelectorAll('input')];
  }
  if (left.length < 2 || right.length < 2) {
    const unique = [...new Set([
      ...panel.querySelectorAll('.el-date-range-picker__time-header input'),
      ...panel.querySelectorAll('.el-date-range-picker__editor'),
    ])];
    if (unique.length >= 4) {
      left = unique.slice(0, 2);
      right = unique.slice(2, 4);
    }
  }
  if (left.length < 2 || right.length < 2) {
    return {
      ok: false,
      reason: 'no-time-editors',
      left: left.length,
      right: right.length,
    };
  }
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    'value',
  ).set;
  const assign = (el, value) => {
    setter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  };
  assign(left[0], startDate);
  assign(left[1], startTime);
  assign(right[0], endDate);
  assign(right[1], endTime);
  return {
    ok: true,
    values: [left[0].value, left[1].value, right[0].value, right[1].value],
  };
}"""

CLICK_RECEIPT_CHECKBOX_JS = r"""({ receiptNo, lineNo }) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
  const tables = [...document.querySelectorAll('.el-table')];
  if (!tables.length) return 'no-table';
  const table = tables
    .map((candidate) => ({
      candidate,
      rowCount: candidate.querySelectorAll('.el-table__body-wrapper tbody tr').length,
    }))
    .sort((a, b) => b.rowCount - a.rowCount)[0].candidate;
  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')]
    .map((th) => clean(th.innerText));
  const receiptIdx = headers.findIndex((header) => header.includes('收货单号'));
  const lineIdx = headers.findIndex(
    (header) => header.includes('收货单行号') || header === '行号',
  );
  const bodyRows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')];
  let index = -1;
  bodyRows.forEach((tr, rowIndex) => {
    const cells = [...tr.querySelectorAll(':scope > td')];
    const receipt = receiptIdx >= 0 ? clean(cells[receiptIdx] && cells[receiptIdx].innerText) : '';
    const line = lineIdx >= 0 ? clean(cells[lineIdx] && cells[lineIdx].innerText) : '';
    const blob = clean(tr.innerText);
    if (
      (receipt === receiptNo && line === lineNo)
      || (blob.includes(receiptNo) && blob.split(/\s+/).includes(lineNo))
    ) {
      index = rowIndex;
    }
  });
  if (index < 0) return 'row-missing';
  const fixed = table.querySelector('.el-table__fixed-left, .el-table__fixed');
  const sourceRows = fixed
    ? [...fixed.querySelectorAll('.el-table__body-wrapper tbody tr')]
    : bodyRows;
  const row = sourceRows[index] || bodyRows[index];
  if (!row) return 'row-missing';
  const box = [...row.querySelectorAll('.el-checkbox__inner, .el-checkbox')]
    .find((el) => visible(el));
  if (!box) return 'checkbox-missing';
  box.click();
  return 'ok';
}"""


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def resolve_captcha_code(src):
    text = _clean(src).lower()
    for key, code in CAPTCHA_CODES.items():
        if key in text:
            return code
    return None


def parse_ymd(value):
    match = DATE_RE.fullmatch(_clean(value))
    if not match:
        raise RpaFatalError(
            "STMT_DATE_RANGE_INVALID",
            "dateStart/dateEnd must be YYYY-MM-DD",
        )
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise RpaFatalError(
            "STMT_DATE_RANGE_INVALID",
            "dateStart/dateEnd must be a real calendar date",
        ) from exc


def inbound_range_datetimes(start, end):
    """Client 只给日期；正式面板开始 00:00:00、结束 23:59:59。"""
    return (
        f"{start.isoformat()} {START_TIME}",
        f"{end.isoformat()} {END_TIME}",
    )


def applied_range_is_valid(actual_start, actual_end, start, end):
    expected_start, expected_end = inbound_range_datetimes(start, end)
    return expected_start in _clean(actual_start) and expected_end in _clean(actual_end)


def month_nav_action(left_year, left_month, target_year, target_month, right_year=None, right_month=None):
    if (left_year, left_month) == (target_year, target_month):
        return "visible-left"
    if right_year is not None and (right_year, right_month) == (target_year, target_month):
        return "visible-right"
    left = left_year * 12 + left_month
    target = target_year * 12 + target_month
    if target < left:
        return "year-prev" if target_year < left_year else "month-prev"
    if right_year is not None:
        right = right_year * 12 + right_month
        if target > right:
            return "year-next" if target_year > right_year else "month-next"
        return "visible-right"
    return "year-next" if target_year > left_year else "month-next"


def parse_lines(raw_lines):
    if not isinstance(raw_lines, list) or not raw_lines:
        raise RpaFatalError("STMT_LINES_REQUIRED", "lines are required")
    lines = []
    for item in raw_lines:
        if not isinstance(item, Mapping):
            continue
        receipt_no = _clean(
            item.get("receiptNo") or item.get("receipt_no") or item.get("收货单号")
        )
        line_no = _clean(
            item.get("lineNo")
            or item.get("line_no")
            or item.get("收货单行号")
            or item.get("行号")
        )
        order_no = _clean(
            item.get("orderNo") or item.get("order_no") or item.get("订单编号")
        )
        if receipt_no and line_no:
            lines.append({"receiptNo": receipt_no, "lineNo": line_no, "orderNo": order_no})
    if not lines:
        raise RpaFatalError("STMT_LINES_EMPTY", "no valid receipt lines")
    return lines


def resolve_check_amount(raw_input, lines):
    raw = raw_input.get("localAmount") or raw_input.get("local_amount")
    if raw is not None and str(raw).strip() != "":
        try:
            return str(Decimal(str(raw).replace(",", "")).quantize(Decimal("0.01")))
        except (InvalidOperation, ValueError) as exc:
            raise RpaFatalError("STMT_AMOUNT_INVALID", "localAmount is invalid") from exc
    total = Decimal("0.00")
    for item in lines if isinstance(lines, list) else []:
        if not isinstance(item, Mapping):
            continue
        amount = (
            item.get("taxIncludedAmount")
            or item.get("价税合计")
            or item.get("可立账价税合计（元）")
        )
        if amount is None:
            continue
        total += Decimal(str(amount).replace(",", ""))
    return str(total.quantize(Decimal("0.01")))


def generate_result(*, dry_run, check_amount, check_date, line_count, button_found=True):
    payload = {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "checkDate": check_date,
        "checkAmount": check_amount,
        "selectedLineCount": line_count,
        "committed": not dry_run,
        "dryRun": bool(dry_run),
        "generateButtonFound": bool(button_found),
    }
    if dry_run:
        payload["blockedAction"] = "generate_statement"
    return payload


async def _safe_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return


async def _safe_emit(ctx, event_type, message="", payload=None):
    try:
        await ctx.events.emit(event_type, message=message, payload=payload or {})
    except Exception:
        return


class ReceiptListAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.page
        self.selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}

    def selector(self, name, **values):
        value = self.selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError(
                "FLOW_SELECTOR_MISSING",
                f"Required selector is missing: {name}",
            )
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    async def login(self):
        await login_official_srm(self.ctx, selector=self.selector)

    async def _wait_loading_done(self):
        try:
            await self.page.locator(self.selector("loading_mask")).wait_for(
                state="hidden", timeout=15000
            )
        except Exception:
            pass

    async def open_receipt_list(self, date_start: str, date_end: str):
        step_id = "srm.open_receipt_list"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Opening receipt list",
            payload={"stepId": step_id, "stepType": step_id},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        await self.page.goto(
            f"{portal_root}/#/order/receivingList", wait_until="domcontentloaded"
        )
        page = self.page.locator(self.selector("receipt_page"))
        try:
            await page.wait_for(state="visible", timeout=15000)
        except Exception as exc:
            await _safe_screenshot(self.ctx, "stmt-receipt-page-missing", step_id)
            raise RpaBusinessError(
                "SRM_STMT_RECEIPT_PAGE_MISSING",
                "Receipt list page is unavailable",
            ) from exc
        await self.pick_inbound_confirm_range(date_start, date_end)
        await self.select_form_option(RECONCILE_STATUS_LABEL, UNSUBMITTED_STATUS)
        await self.page.locator(self.selector("search_button")).click(timeout=4000)
        await self._wait_loading_done()
        await self.page.wait_for_timeout(500)
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Receipt list opened",
            payload={"stepId": step_id},
        )

    async def pick_inbound_confirm_range(self, date_start: str, date_end: str):
        start = parse_ymd(date_start)
        end = parse_ymd(date_end)
        if start > end:
            raise RpaFatalError(
                "STMT_DATE_RANGE_INVALID",
                "dateStart must be on or before dateEnd",
            )
        editor = self.page.locator(self.selector("date_range")).first
        try:
            await editor.wait_for(state="visible", timeout=8000)
            await editor.click(timeout=4000)
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Inbound confirm date range is unavailable",
            ) from exc
        panel = self.page.locator(self.selector("date_picker")).first
        try:
            await panel.wait_for(state="visible", timeout=5000)
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Inbound confirm date picker did not open",
            ) from exc
        await self._pick_calendar_day(start)
        await self._pick_calendar_day(end)
        await self._apply_range_datetimes(start, end)
        confirm = self.page.locator(self.selector("date_picker_confirm")).first
        try:
            await confirm.click(timeout=4000)
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Inbound confirm date picker confirm is unavailable",
            ) from exc
        try:
            await panel.wait_for(state="hidden", timeout=4000)
        except Exception:
            await self.page.keyboard.press("Escape")
        await self._assert_applied_range(start, end)

    async def _read_picker_months(self):
        payload = await self.page.evaluate(READ_PICKER_MONTHS_JS)
        months = payload.get("months") if isinstance(payload, Mapping) else []
        parsed = []
        for item in months if isinstance(months, list) else []:
            if not isinstance(item, Mapping):
                continue
            year = item.get("year")
            month = item.get("month")
            if isinstance(year, int) and isinstance(month, int):
                parsed.append((year, month))
        return parsed

    async def _ensure_month_visible(self, target: date):
        for _ in range(36):
            months = await self._read_picker_months()
            if not months:
                raise RpaRetryableError(
                    "SRM_STMT_DATE_RANGE_MISSING",
                    "Inbound confirm date picker months are unavailable",
                )
            left_year, left_month = months[0]
            right = months[1] if len(months) > 1 else (None, None)
            action = month_nav_action(
                left_year,
                left_month,
                target.year,
                target.month,
                right[0],
                right[1],
            )
            if action.startswith("visible"):
                return
            selector_name = {
                "year-prev": "date_picker_prev_year",
                "month-prev": "date_picker_prev_month",
                "month-next": "date_picker_next_month",
                "year-next": "date_picker_next_year",
            }[action]
            await self.page.locator(self.selector(selector_name)).first.click(timeout=2000)
            await self.page.wait_for_timeout(150)
        raise RpaRetryableError(
            "SRM_STMT_DATE_RANGE_MISSING",
            "Inbound confirm date picker could not reach the requested month",
        )

    async def _pick_calendar_day(self, target: date):
        await self._ensure_month_visible(target)
        result = await self.page.evaluate(
            CLICK_PICKER_DAY_JS,
            {"year": target.year, "month": target.month, "day": target.day},
        )
        if result != "ok":
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                f"Inbound confirm calendar day is unavailable: {target.isoformat()}",
            )
        await self.page.wait_for_timeout(150)

    async def _apply_range_datetimes(self, start, end):
        payload = await self.page.evaluate(
            SET_PICKER_RANGE_JS,
            {
                "startDate": start.isoformat(),
                "startTime": START_TIME,
                "endDate": end.isoformat(),
                "endTime": END_TIME,
            },
        )
        if not isinstance(payload, Mapping) or not payload.get("ok"):
            reason = payload.get("reason") if isinstance(payload, Mapping) else "invalid"
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                f"Inbound confirm start/end times could not be set ({reason})",
            )
        values = payload.get("values") or []
        if len(values) < 4 or values[1] != START_TIME or values[3] != END_TIME:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                f"Inbound confirm times are wrong in picker: {values}",
            )

    async def _assert_applied_range(self, start, end):
        expected_start, expected_end = inbound_range_datetimes(start, end)
        box = self.page.locator(self.selector("date_range")).first
        inputs = box.locator("input")
        if await inputs.count() < 2:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Inbound confirm date range inputs are unavailable after confirm",
            )
        actual_start = _clean(await inputs.nth(0).input_value())
        actual_end = _clean(await inputs.nth(1).input_value())
        if not applied_range_is_valid(actual_start, actual_end, start, end):
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Inbound confirm range must be "
                f"{expected_start} - {expected_end}, got {actual_start} - {actual_end}",
            )

    async def select_form_option(self, label, option):
        item = self.page.locator(".el-form-item").filter(
            has=self.page.locator(".el-form-item__label", has_text=label)
        ).first
        if await item.count() == 0:
            raise RpaRetryableError(
                "SRM_STMT_FILTER_UNAVAILABLE",
                f"Supplier portal filter is missing: {label}",
            )
        trigger = item.locator(".el-select input, .el-input__inner, input").first
        await trigger.click(timeout=4000)
        await self.page.wait_for_timeout(400)
        option_loc = self.page.locator(
            ".el-select-dropdown:visible li, .el-select-dropdown:visible .el-option"
        ).filter(has_text=option).first
        try:
            await option_loc.click(timeout=4000)
        except Exception as exc:
            await self.page.keyboard.press("Escape")
            raise RpaRetryableError(
                "SRM_STMT_FILTER_UNAVAILABLE",
                f"Supplier portal filter option is missing: {label}={option}",
            ) from exc
        await self.page.wait_for_timeout(200)

    async def select_lines(self, lines):
        missing = []
        for line in lines:
            result = await self.page.evaluate(
                CLICK_RECEIPT_CHECKBOX_JS,
                {"receiptNo": line["receiptNo"], "lineNo": line["lineNo"]},
            )
            if result != "ok":
                missing.append(f"{line['receiptNo']}/{line['lineNo']}")
            await self.page.wait_for_timeout(150)
        if missing:
            raise RpaBusinessError(
                "SRM_STMT_GENERATE_MISMATCH",
                f"receipt lines not found on page: {', '.join(missing[:8])}",
            )

    async def locate_generate_button(self):
        button = self.page.locator(self.selector("generate_button")).first
        try:
            await button.wait_for(state="visible", timeout=8000)
        except Exception as exc:
            await _safe_screenshot(self.ctx, "stmt-generate-button-missing", "srm.generate")
            raise RpaBusinessError(
                "SRM_STMT_GENERATE_BUTTON_MISSING",
                "Generate statement button is not visible",
            ) from exc
        disabled = False
        try:
            disabled = await button.is_disabled()
        except Exception:
            disabled = False
        classes = _clean(await button.get_attribute("class"))
        if disabled or "is-disabled" in classes:
            await _safe_screenshot(self.ctx, "stmt-generate-button-disabled", "srm.generate")
            raise RpaBusinessError(
                "SRM_STMT_GENERATE_BUTTON_DISABLED",
                "Generate statement button is visible but disabled",
            )
        return button

    async def click_generate(self, button):
        await button.click(timeout=4000)
        toast = self.page.locator(self.selector("success_toast"))
        try:
            await toast.first.wait_for(state="visible", timeout=15000)
        except Exception:
            await _safe_screenshot(self.ctx, "stmt-generate-no-toast", "srm.generate")
            error = self.page.locator(".el-message--error")
            if await error.count():
                raise RpaBusinessError(
                    "SRM_STMT_GENERATE_FAILED",
                    await error.first.inner_text(),
                )
            raise RpaRetryableError(
                "SRM_STMT_GENERATE_UNCONFIRMED",
                "generate result toast missing",
            )


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")
    raw_input = ctx.input if isinstance(ctx.input, Mapping) else {}
    date_start = _clean(raw_input.get("dateStart") or raw_input.get("date_start"))
    date_end = _clean(raw_input.get("dateEnd") or raw_input.get("date_end"))
    if not date_start or not date_end:
        raise RpaFatalError("STMT_DATE_RANGE_REQUIRED", "dateStart/dateEnd are required")
    parse_ymd(date_start)
    parse_ymd(date_end)
    lines = parse_lines(raw_input.get("lines"))
    check_amount = resolve_check_amount(raw_input, raw_input.get("lines"))
    check_date = date.today().isoformat()
    dry_run = is_dry_run(ctx)

    await ctx.log.info("Starting statement generate Flow", {"dryRun": dry_run})
    adapter = ReceiptListAdapter(ctx)
    await adapter.login()
    await install_write_guard(ctx.page, dry_run=dry_run)
    await adapter.open_receipt_list(date_start, date_end)

    step_id = "srm.generate"
    await _safe_emit(
        ctx,
        "STEP_STARTED",
        message="Selecting receipt lines and locating generate button",
        payload={"stepId": step_id, "stepType": step_id, "dryRun": dry_run},
    )
    await adapter.select_lines(lines)
    button = await adapter.locate_generate_button()
    await _safe_screenshot(ctx, "stmt-generate-button", step_id)
    if dry_run:
        await _safe_emit(
            ctx,
            "STEP_SUCCEEDED",
            message="Generate button found; dry-run skipped the click",
            payload={
                "stepId": step_id,
                "dryRun": True,
                "blockedAction": "generate_statement",
                "selectedLineCount": len(lines),
            },
        )
        return generate_result(
            dry_run=True,
            check_amount=check_amount,
            check_date=check_date,
            line_count=len(lines),
        )
    await adapter.click_generate(button)
    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Statement generated",
        payload={"stepId": step_id, "selectedLineCount": len(lines)},
    )
    return generate_result(
        dry_run=False,
        check_amount=check_amount,
        check_date=check_date,
        line_count=len(lines),
    )
