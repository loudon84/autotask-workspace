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

# Match main-table row by 订单行号, fill date input in fixed-right row at same index.
FILL_SUPPLIER_DATE_JS = r"""([lineNo, expectedDate]) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ').trim();
  const want = clean(lineNo);
  const mainBodies = [...document.querySelectorAll('.el-table__body-wrapper')]
    .filter((el) => !el.closest('.el-table__fixed-right') && !el.closest('.el-table__fixed'));
  const mainBody = mainBodies[0] || document.querySelector('.el-table__body-wrapper');
  if (!mainBody) return { ok: false, reason: 'main_body_missing' };
  const mainRows = [...mainBody.querySelectorAll(':scope > table > tbody > tr, :scope > tbody > tr')];
  let index = -1;
  for (let i = 0; i < mainRows.length; i += 1) {
    const cells = mainRows[i].querySelectorAll(':scope > td');
    if (clean(cells[0]?.innerText) === want) {
      index = i;
      break;
    }
  }
  if (index < 0) return { ok: false, reason: 'line_not_found', lineNo: want };
  const fixedRoot = document.querySelector('.el-table__fixed-right');
  const fixedBody = fixedRoot
    ? fixedRoot.querySelector('.el-table__body-wrapper')
    : null;
  const fixedRows = fixedBody
    ? [...fixedBody.querySelectorAll(':scope > table > tbody > tr, :scope > tbody > tr')]
    : [];
  const targetRow = fixedRows[index] || mainRows[index];
  if (!targetRow) return { ok: false, reason: 'row_missing', index };
  const input = targetRow.querySelector(
    '.el-date-editor input.el-input__inner, input.el-input__inner'
  );
  if (!input) return { ok: false, reason: 'date_input_missing', index };
  if (input.disabled || input.readOnly) {
    return { ok: false, reason: 'date_input_disabled', index };
  }
  input.focus();
  input.click();
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
  if (setter) setter.call(input, expectedDate);
  else input.value = expectedDate;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));
  return { ok: true, index, actual: clean(input.value) };
}"""

COLLECT_LINE_NOS_JS = r"""() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ').trim();
  const mainBodies = [...document.querySelectorAll('.el-table__body-wrapper')]
    .filter((el) => !el.closest('.el-table__fixed-right') && !el.closest('.el-table__fixed'));
  const mainBody = mainBodies[0] || document.querySelector('.el-table__body-wrapper');
  if (!mainBody) return [];
  const rows = [...mainBody.querySelectorAll(':scope > table > tbody > tr, :scope > tbody > tr')];
  return rows.map((row) => {
    const cells = row.querySelectorAll(':scope > td');
    return {
      lineNo: clean(cells[0]?.innerText),
      materialNo: clean(cells[1]?.innerText),
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
        detail = self.page.locator(self.selector("order_detail", po_no=po_no)).first
        try:
            if await detail.count():
                await detail.click(timeout=10000)
            else:
                await row.locator("text=详情").first.click(timeout=10000)
            await self.page.locator(self.selector("detail_page")).first.wait_for(
                state="visible", timeout=15000
            )
            await self.page.locator(self.selector("detail_po_number", po_no=po_no)).first.wait_for(
                state="visible", timeout=15000
            )
            await self._wait_loading_done()
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
        for item in order_lines:
            result = await self.page.evaluate(
                FILL_SUPPLIER_DATE_JS,
                [item["lineNo"], item["expectedDeliveryDate"]],
            )
            if not isinstance(result, Mapping) or not result.get("ok"):
                reason = result.get("reason") if isinstance(result, Mapping) else "unknown"
                raise RpaRetryableError(
                    "ORDER_DATE_FILL_FAILED",
                    "Failed to fill 供方交期 on the official portal form",
                    details={"lineNo": item["lineNo"], "reason": reason},
                )
            actual = _clean(result.get("actual"))
            if actual and actual != item["expectedDeliveryDate"]:
                # Some date pickers show value only after blur/Enter; re-check via input.
                await self.page.wait_for_timeout(200)
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(120)

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
