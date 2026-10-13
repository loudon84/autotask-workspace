"""SRM 签章（正式门户）。

输入：po_no, order_lines[{line_number, expected_delivery_date}]
操作：登录 → 订单详情 → 填供方交期 → 点签章。
dryRun=true：填交期并确认签章按钮可点后截图，不 click。
dryRun=false：点击签章。
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaHumanRequiredError,
    RpaRetryableError,
    install_write_guard,
    is_dry_run,
    login_official_srm,
)

PO_NUMBER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SIGN_SUCCESS_TEXT = "签章成功"
SIGNED_REPLY_STATUS = "已回签"
PENDING_REPLY_STATUS = "待回签"
PENDING_SIGN_STATUS = "待签章"
OUTPUT_SCHEMA_VERSION = "SRM_SIGN_ORDER_OUTPUT_V1"

_CLICK_VISIBLE_DETAIL_JS = r"""(poNo) => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const isVisible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return false;
    const style = window.getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) {
      return false;
    }
    return true;
  };
  const findDetail = (row) => [...row.querySelectorAll('button, a, .el-button, .el-link, span')].find((el) => {
    const text = clean(el.innerText);
    return (text === '详情' || text === '查看') && isVisible(el);
  });
  const mainBodies = [...document.querySelectorAll('.el-table__body-wrapper tbody')].filter(
    (body) => !body.closest('.el-table__fixed-right, .el-table__fixed')
  );
  let index = -1;
  for (const body of mainBodies) {
    const rows = [...body.querySelectorAll(':scope > tr')];
    index = rows.findIndex((row) => clean(row.innerText).includes(poNo));
    if (index >= 0) break;
  }
  if (index < 0) return false;
  const rowsToTry = [];
  const fixedBody = document.querySelector(
    '.el-table__fixed-right .el-table__body-wrapper tbody'
  );
  if (fixedBody) {
    const fixedRow = fixedBody.querySelectorAll(':scope > tr')[index];
    if (fixedRow) rowsToTry.push(fixedRow);
  }
  for (const body of mainBodies) {
    const row = body.querySelectorAll(':scope > tr')[index];
    if (row) rowsToTry.push(row);
  }
  for (const row of rowsToTry) {
    const btn = findDetail(row);
    if (btn) {
      const target = btn.closest('button, a, .el-button, .el-link') || btn;
      target.click();
      return true;
    }
  }
  return false;
}"""

# Multi-row contract (official detail table):
# 1) 订单行号 lives in the MAIN scrollable body.
# 2) Same row index in FIXED-RIGHT body (`el-table__fixed-body-wrapper`).
# 3) 供方交期 is the FIRST column of that fixed-right row
#    (fixed columns: 供方交期 | 欠交数量 | 操作).
# Never mark "first visible date on page" — that breaks multi-line orders.
MARK_SUPPLIER_DATE_JS = r"""(lineNo) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ').trim();
  const want = clean(lineNo);
  document.querySelectorAll('[data-autotask-supplier-date]').forEach((el) => {
    el.removeAttribute('data-autotask-supplier-date');
  });
  const dataRows = (root) => {
    if (!root) return [];
    const tbody = root.querySelector('table > tbody') || root.querySelector('tbody');
    if (!tbody) return [];
    return [...tbody.querySelectorAll(':scope > tr')].filter((row) => {
      return row.querySelectorAll(':scope > td').length > 0;
    });
  };
  const lineNoOf = (row) => {
    const cells = [...row.querySelectorAll(':scope > td')];
    for (const cell of cells) {
      const text = clean(cell.innerText);
      if (!text) continue;
      if (cell.querySelector('input[type="checkbox"], .el-checkbox')) continue;
      return text;
    }
    return '';
  };
  const dateInputInFirstFixedCell = (row) => {
    const firstCell = row.querySelector(':scope > td');
    if (!firstCell) return null;
    return firstCell.querySelector(
      '.el-date-editor input.el-input__inner, .el-date-editor input, input.el-input__inner'
    );
  };
  const mainBodies = [...document.querySelectorAll('.el-table__body-wrapper')].filter(
    (el) => !el.closest('.el-table__fixed-right') && !el.closest('.el-table__fixed')
  );
  let index = -1;
  let mainRowCount = 0;
  for (const body of mainBodies) {
    const rows = dataRows(body);
    mainRowCount = Math.max(mainRowCount, rows.length);
    index = rows.findIndex((row) => lineNoOf(row) === want);
    if (index >= 0) break;
  }
  if (index < 0) {
    return { ok: false, reason: 'line_not_found', lineNo: want, mainRowCount };
  }
  // Fixed-right body uses fixed-body-wrapper in Element UI.
  const fixedRoots = [
    ...document.querySelectorAll(
      '.el-table__fixed-right .el-table__fixed-body-wrapper, .el-table__fixed-right .el-table__body-wrapper'
    ),
  ];
  for (const fixedBody of fixedRoots) {
    const fixedRow = dataRows(fixedBody)[index];
    if (!fixedRow) continue;
    const input = dateInputInFirstFixedCell(fixedRow);
    if (!input) continue;
    input.setAttribute('data-autotask-supplier-date', want);
    return {
      ok: true,
      index,
      marked: true,
      mainRowCount,
      fixedRowCount: dataRows(fixedBody).length,
      readonly: !!input.readOnly,
      disabled: !!input.disabled,
      placeholder: clean(input.getAttribute('placeholder')),
      value: clean(input.value),
      inFixedRight: true,
      fixedFirstColumn: true,
    };
  }
  return {
    ok: false,
    reason: 'date_input_missing',
    index,
    lineNo: want,
    mainRowCount,
    fixedRootCount: fixedRoots.length,
  };
}"""

READ_MARKED_DATE_JS = r"""(lineNo) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ').trim();
  const input = document.querySelector(`[data-autotask-supplier-date="${clean(lineNo)}"]`);
  if (!input) return { ok: false, reason: 'marked_missing' };
  return { ok: true, value: clean(input.value) };
}"""

COLLECT_LINE_NOS_JS = r"""() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ').trim();
  const lineNoOf = (row) => {
    const cells = [...row.querySelectorAll(':scope > td')];
    for (const cell of cells) {
      const text = clean(cell.innerText);
      if (!text) continue;
      if (cell.querySelector('input[type="checkbox"], .el-checkbox')) continue;
      return text;
    }
    return '';
  };
  const mainBodies = [...document.querySelectorAll('.el-table__body-wrapper')]
    .filter((el) => !el.closest('.el-table__fixed-right') && !el.closest('.el-table__fixed'));
  const mainBody = mainBodies[0] || document.querySelector('.el-table__body-wrapper');
  if (!mainBody) return [];
  const tbody = mainBody.querySelector('table > tbody') || mainBody.querySelector('tbody');
  if (!tbody) return [];
  const rows = [...tbody.querySelectorAll(':scope > tr')].filter(
    (row) => row.querySelectorAll(':scope > td').length > 0
  );
  return rows.map((row, index) => {
    const cells = [...row.querySelectorAll(':scope > td')].filter(
      (cell) => !cell.querySelector('input[type="checkbox"], .el-checkbox')
    );
    return {
      lineNo: lineNoOf(row),
      materialNo: clean(cells[1]?.innerText),
      index,
    };
  }).filter((item) => item.lineNo);
}"""


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_order_lines(raw_input):
    value = raw_input if isinstance(raw_input, Mapping) else {}
    raw_lines = value.get("order_lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "order_lines is required and must be a non-empty array",
        )
    lines = []
    for raw in raw_lines:
        if not isinstance(raw, Mapping):
            continue
        line_no = _clean(raw.get("line_number") or raw.get("lineNo"))
        expected_date = _clean(
            raw.get("expected_delivery_date") or raw.get("expectedDeliveryDate")
        )
        if not line_no or not expected_date:
            continue
        if not DATE_PATTERN.fullmatch(expected_date):
            raise RpaBusinessError(
                "FLOW_INPUT_INVALID",
                "expected_delivery_date must be YYYY-MM-DD",
                details={"lineNo": line_no, "expectedDeliveryDate": expected_date},
            )
        lines.append({"lineNo": line_no, "expectedDeliveryDate": expected_date})
    if not lines:
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "order_lines has no usable line_number/expected_delivery_date pairs",
        )
    return lines


def validate_input(raw_input):
    value = raw_input if isinstance(raw_input, Mapping) else {}
    po_no = _clean(value.get("po_no")).upper()
    if not PO_NUMBER_PATTERN.fullmatch(po_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Customer purchase order number is missing or invalid",
        )
    return po_no, parse_order_lines(value)


def sign_result(*, dry_run: bool, po_no: str, line_count: int, reply_status: str, idempotent=False):
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "poNo": po_no,
        "signed": (not dry_run) or idempotent,
        "dryRun": bool(dry_run),
        "replyStatus": reply_status,
        "idempotent": bool(idempotent),
        "lineCount": line_count,
        "tempE2eBackfill": False,
        "filledSupplierDates": True,
    }


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
        await login_official_srm(self.ctx, selector=self.selector)

    async def _wait_loading_done(self):
        mask = self.page.locator(self.selector("loading_mask"))
        try:
            if await mask.count():
                await mask.first.wait_for(state="hidden", timeout=30000)
        except Exception:
            pass

    async def _click_visible_detail(self, po_no):
        try:
            if await self.page.evaluate(_CLICK_VISIBLE_DETAIL_JS, po_no):
                return
        except Exception:
            pass
        fixed = self.page.locator(".el-table__fixed-right").get_by_text("详情", exact=True)
        if await fixed.count():
            await fixed.first.click(timeout=8000)
            return
        await self.page.get_by_text("详情", exact=True).locator("visible=true").first.click(
            timeout=8000
        )

    async def _wait_detail_ready(self, po_no):
        deadline = asyncio.get_running_loop().time() + 20
        while asyncio.get_running_loop().time() < deadline:
            hash_value = ""
            try:
                hash_value = await self.page.evaluate("() => location.hash || ''")
            except Exception:
                hash_value = ""
            if f"/detail/{po_no}" in hash_value or "/detail/" in hash_value:
                break
            detail_tab = self.page.locator(".el-tabs__item:has-text('订单详情'):visible").first
            try:
                if await detail_tab.count() and await detail_tab.is_visible():
                    await detail_tab.click(timeout=2000)
            except Exception:
                pass
            await self.page.wait_for_timeout(250)
        await self._wait_loading_done()
        await self.page.locator(self.selector("detail_page")).first.wait_for(
            state="visible", timeout=15000
        )
        await self.page.locator(self.selector("detail_po_number", po_no=po_no)).first.wait_for(
            state="visible", timeout=15000
        )

    async def open_order_detail(self, po_no):
        step_id = "srm.search_po"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Searching for customer purchase order",
            payload={"stepId": step_id, "stepType": step_id, "poNo": po_no},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        opened = False
        for hash_path in ("/order/list", "/supplier/orders"):
            await self.page.goto(
                f"{portal_root}/#{hash_path.lstrip('#')}",
                wait_until="domcontentloaded",
            )
            try:
                await self.page.locator(self.selector("order_page")).first.wait_for(
                    state="visible",
                    timeout=8000,
                )
                opened = True
                break
            except Exception:
                continue
        if not opened:
            raise RpaRetryableError(
                "ORDER_LIST_UNAVAILABLE",
                "Supplier portal order list could not be opened",
            )
        try:
            await self.page.fill(self.selector("po_number"), po_no)
            await self.page.click(self.selector("search_button"))
            await self._wait_loading_done()
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_SEARCH_UNAVAILABLE",
                "Customer purchase order search could not be completed",
            ) from exc
        row = self.page.locator(self.selector("order_row", po_no=po_no)).first
        try:
            await row.wait_for(state="visible", timeout=10000)
        except Exception as exc:
            raise RpaBusinessError(
                "BUSINESS_NOT_FOUND",
                "Customer purchase order was not found",
            ) from exc
        try:
            await self._click_visible_detail(po_no)
            await self._wait_detail_ready(po_no)
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

    async def collect_line_nos(self):
        try:
            result = await self.page.evaluate(COLLECT_LINE_NOS_JS)
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
        tags = self.page.locator(self.selector("reply_status_tag"))
        try:
            count = await tags.count()
            for index in range(min(count, 20)):
                text = _clean(await tags.nth(index).inner_text())
                if text in {SIGNED_REPLY_STATUS, PENDING_REPLY_STATUS, PENDING_SIGN_STATUS}:
                    return text
        except Exception:
            pass
        body = _clean(await self.page.locator("body").inner_text())
        for label in (SIGNED_REPLY_STATUS, PENDING_REPLY_STATUS, PENDING_SIGN_STATUS):
            if label in body:
                return label
        raise RpaRetryableError(
            "ORDER_REPLY_STATUS_UNAVAILABLE",
            "Order reply status could not be read",
        )

    async def ensure_signable(self):
        try:
            sign_button = self.page.locator(self.selector("sign")).first
            await sign_button.wait_for(state="visible", timeout=10000)
            if not await sign_button.is_enabled():
                raise RpaBusinessError(
                    "ORDER_NOT_EDITABLE",
                    "Customer purchase order cannot be signed",
                )
            return sign_button
        except RpaBusinessError:
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_EDITABILITY_UNAVAILABLE",
                "Order sign action state could not be verified",
            ) from exc

    async def _supplier_date_field(self, line_no):
        marked = await self.page.evaluate(MARK_SUPPLIER_DATE_JS, line_no)
        if not isinstance(marked, Mapping) or not marked.get("ok"):
            reason = marked.get("reason") if isinstance(marked, Mapping) else "unknown"
            raise RpaRetryableError(
                "ORDER_DATE_FILL_FAILED",
                "供方交期 input was not found on the portal detail",
                details={"lineNo": line_no, "reason": reason, "mark": marked},
            )
        field = self.page.locator(f'[data-autotask-supplier-date="{line_no}"]').first
        try:
            await field.wait_for(state="attached", timeout=3000)
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DATE_FILL_FAILED",
                "Marked 供方交期 input was not attached",
                details={"lineNo": line_no},
            ) from exc
        # Scroll into view; fixed-right inputs may be outside the main viewport box.
        try:
            await field.evaluate("el => el.scrollIntoView({block:'center', inline:'center'})")
        except Exception:
            pass
        return field, marked

    async def _read_supplier_date(self, line_no, field):
        try:
            actual = _clean(await field.input_value())
            if actual:
                return actual
        except Exception:
            pass
        result = await self.page.evaluate(READ_MARKED_DATE_JS, line_no)
        if isinstance(result, Mapping) and result.get("ok"):
            return _clean(result.get("value"))
        return ""

    async def _fill_date_via_panel(self, expected_date):
        """Type YYYY-MM-DD into the open Element date panel. Do not click day cells (multi-row unsafe)."""
        panel = self.page.locator(".el-picker-panel:visible, .el-date-picker:visible").first
        try:
            await panel.wait_for(state="visible", timeout=3000)
        except Exception:
            return False
        panel_input = panel.locator("input.el-input__inner:visible").first
        try:
            if await panel_input.count():
                await panel_input.click(timeout=2000)
                await panel_input.fill("")
                await panel_input.type(expected_date, delay=20)
                await panel_input.press("Enter")
                return True
        except Exception:
            return False
        return False

    async def _verify_supplier_dates(self, expected_by_line):
        """Remount marks per line and assert every expected date is still present."""
        mismatches = []
        for line_no, expected_date in expected_by_line.items():
            field, _meta = await self._supplier_date_field(line_no)
            actual = await self._read_supplier_date(line_no, field)
            if actual != expected_date:
                mismatches.append(
                    {"lineNo": line_no, "expected": expected_date, "actual": actual}
                )
        if mismatches:
            raise RpaRetryableError(
                "ORDER_DATE_FILL_FAILED",
                "One or more 供方交期 values did not retain AutoTask dates",
                details={"mismatches": mismatches},
            )

    async def fill_supplier_delivery_dates(self, order_lines):
        portal_lines = await self.collect_line_nos()
        portal_nos = {item["lineNo"] for item in portal_lines}
        missing = [item["lineNo"] for item in order_lines if item["lineNo"] not in portal_nos]
        if missing:
            raise RpaBusinessError(
                "ORDER_LINE_NOT_FOUND",
                "Some AutoTask lines were not found on the portal detail",
                details={"missingLineNumbers": missing},
            )
        # Stable order: fill by portal table order when possible, else input order.
        portal_order = {item["lineNo"]: idx for idx, item in enumerate(portal_lines)}
        ordered_lines = sorted(
            order_lines,
            key=lambda item: portal_order.get(item["lineNo"], 10_000),
        )
        expected_by_line = {
            item["lineNo"]: item["expectedDeliveryDate"] for item in ordered_lines
        }
        for item in ordered_lines:
            line_no = item["lineNo"]
            expected_date = item["expectedDeliveryDate"]
            field, meta = await self._supplier_date_field(line_no)
            if await field.is_disabled() or bool(meta.get("disabled")):
                raise RpaBusinessError(
                    "ORDER_NOT_EDITABLE",
                    "The supplier delivery date field is not editable",
                    details={"lineNo": line_no, "index": meta.get("index")},
                )
            await field.click(timeout=5000, force=True)
            await self.page.wait_for_timeout(150)
            typed = False
            try:
                # Some Element date inputs are readonly; ignore fill errors and use panel.
                await field.fill("")
                await field.type(expected_date, delay=25)
                await field.press("Enter")
                typed = True
            except Exception:
                typed = False
            if not typed or await self._read_supplier_date(line_no, field) != expected_date:
                await self._fill_date_via_panel(expected_date)
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
            await self.page.wait_for_timeout(200)
            # Close any leftover panel before moving to the next row.
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
            actual = await self._read_supplier_date(line_no, field)
            if actual != expected_date:
                raise RpaRetryableError(
                    "ORDER_DATE_FILL_FAILED",
                    "供方交期 did not retain the AutoTask delivery date",
                    details={
                        "lineNo": line_no,
                        "index": meta.get("index"),
                        "expected": expected_date,
                        "actual": actual,
                        "inFixedRight": meta.get("inFixedRight"),
                    },
                )
        # Final whole-table check so later rows did not wipe earlier ones.
        await self._verify_supplier_dates(expected_by_line)

    async def _wait_for_action_result(self):
        success = self.page.locator(self.selector("sign_success"))
        error = self.page.locator(self.selector("sign_error"))
        for _ in range(75):
            if await success.count() and await success.first.is_visible():
                message = _clean(await success.first.inner_text())
                if SIGN_SUCCESS_TEXT in message:
                    return message[:500]
            if await error.count() and await error.first.is_visible():
                message = _clean(await error.first.inner_text())[:500]
                raise RpaBusinessError(
                    "ORDER_SIGN_REJECTED",
                    message or "Supplier portal rejected the sign action",
                )
            await self.page.wait_for_timeout(200)
        raise RpaHumanRequiredError(
            "ORDER_SIGN_OUTCOME_UNKNOWN",
            "Supplier portal sign result requires manual verification",
        )

    async def sign_and_verify(self, po_no, sign_button):
        try:
            await sign_button.click(timeout=10000)
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
                "签章结果无法自动确认，请在 SRM 人工核对后再继续",
            ) from exc

        try:
            await self.page.locator(self.selector("detail_po_number", po_no=po_no)).first.wait_for(
                state="visible", timeout=15000
            )
            status = ""
            for _ in range(20):
                status = await self.reply_status()
                if status in {SIGNED_REPLY_STATUS, PENDING_REPLY_STATUS}:
                    return success_message, status
                await self.page.wait_for_timeout(200)
            if SIGN_SUCCESS_TEXT in success_message:
                return success_message, PENDING_REPLY_STATUS
            raise RpaHumanRequiredError(
                "ORDER_SIGN_STATUS_UNCONFIRMED",
                "签章后未能确认订单回复状态",
                details={"replyStatus": status},
            )
        except asyncio.CancelledError:
            raise RpaHumanRequiredError(
                "ORDER_SIGN_STATUS_UNCONFIRMED",
                "签章后订单状态需人工核对",
            ) from None
        except RpaHumanRequiredError:
            raise
        except Exception as exc:
            raise RpaHumanRequiredError(
                "ORDER_SIGN_STATUS_UNCONFIRMED",
                "签章后订单状态需人工核对",
            ) from exc


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError(
            "PORTAL_URL_MISSING",
            "Supplier portal URL is unavailable",
        )
    po_no, order_lines = validate_input(getattr(ctx, "input", None))
    dry_run = is_dry_run(ctx)
    await ctx.log.info(
        "Starting official supplier portal sign Flow",
        {
            "poNo": po_no,
            "dryRun": dry_run,
            "orderLineCount": len(order_lines),
        },
    )

    adapter = SupplierPortalSignAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)

    reply_status = await adapter.reply_status()
    if reply_status in {SIGNED_REPLY_STATUS, PENDING_REPLY_STATUS}:
        portal_lines = await adapter.collect_line_nos()
        await _safe_emit(
            ctx,
            "STEP_SUCCEEDED",
            message="Order already signed or pending counter-signature",
            payload={
                "stepId": "srm.idempotency",
                "poNo": po_no,
                "replyStatus": reply_status,
                "dryRun": dry_run,
            },
        )
        return sign_result(
            dry_run=dry_run,
            po_no=po_no,
            line_count=len(portal_lines),
            reply_status=reply_status,
            idempotent=True,
        )

    fill_step = "srm.fill_supplier_delivery_dates"
    await ctx.events.emit(
        "STEP_STARTED",
        message="Filling AutoTask delivery dates into 供方交期",
        payload={
            "stepId": fill_step,
            "stepType": fill_step,
            "poNo": po_no,
            "lineCount": len(order_lines),
        },
    )
    await adapter.fill_supplier_delivery_dates(order_lines)
    await _safe_screenshot(ctx, "supplier-portal-dates-filled", fill_step)
    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Supplier delivery dates filled on the portal form",
        payload={"stepId": fill_step, "poNo": po_no, "lineCount": len(order_lines)},
    )

    # Guard after fill: official dates only POST on 签章; block that write in dryRun.
    await install_write_guard(ctx.page, dry_run=dry_run)
    sign_button = await adapter.ensure_signable()
    step_id = "srm.sign_order"
    await ctx.events.emit(
        "STEP_STARTED",
        message="Locating sign button on customer purchase order",
        payload={
            "stepId": step_id,
            "stepType": step_id,
            "poNo": po_no,
            "lineCount": len(order_lines),
            "dryRun": dry_run,
        },
    )
    await _safe_screenshot(ctx, "supplier-portal-sign-ready", step_id)
    if dry_run:
        await _safe_emit(
            ctx,
            "STEP_SUCCEEDED",
            message="Sign button found; dry-run skipped the click",
            payload={
                "stepId": step_id,
                "dryRun": True,
                "blockedAction": "sign_order",
                "lineCount": len(order_lines),
            },
        )
        return sign_result(
            dry_run=True,
            po_no=po_no,
            line_count=len(order_lines),
            reply_status=PENDING_SIGN_STATUS,
        )

    try:
        _message, reply_status = await adapter.sign_and_verify(po_no, sign_button)
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
    return sign_result(
        dry_run=False,
        po_no=po_no,
        line_count=len(order_lines),
        reply_status=reply_status,
    )
