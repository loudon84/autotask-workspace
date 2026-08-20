"""SRM 收货列表查询（对账单生成前）。

输入：dateStart / dateEnd
输出：{ schemaVersion, portalUrl, totalRows, rows[] }
"""

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
OUTPUT_SCHEMA_VERSION = "SRM_STMT_RECEIPTS_OUTPUT_V1"
MAX_PAGES = 50
UNSUBMITTED_STATUS = "未提交"

COLLECT_RECEIPTS_JS = r"""() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const tables = [...document.querySelectorAll('.el-table')];
  if (!tables.length) return null;
  const table = tables
    .map((candidate) => ({
      candidate,
      rowCount: candidate.querySelectorAll('.el-table__body-wrapper tbody tr').length,
    }))
    .sort((a, b) => b.rowCount - a.rowCount)[0].candidate;
  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')]
    .map((th) => clean(th.innerText));
  const rows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')].map((tr) => {
    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
    const row = {};
    headers.forEach((header, index) => {
      if (header) row[header] = cells[index] || '';
    });
    return row;
  });
  return { headers, rows };
}"""


def _clean(value):
    return str(value or "").replace("\u00a0", " ").strip()


def resolve_captcha_code(src):
    text = _clean(src).lower()
    for key, code in CAPTCHA_CODES.items():
        if key in text:
            return code
    return None


def normalize_receipt_row(raw):
    if not isinstance(raw, Mapping):
        return None
    receipt_no = _clean(
        raw.get("收货单号") or raw.get("receiptNo") or raw.get("receipt_no")
    )
    line_no = _clean(
        raw.get("收货单行号") or raw.get("lineNo") or raw.get("line_no") or raw.get("行号")
    )
    if not receipt_no or not line_no:
        return None
    amount = _clean(
        raw.get("可立账价税合计（元）")
        or raw.get("可立账价税合计")
        or raw.get("价税合计")
        or raw.get("taxIncludedAmount")
    ).replace(",", "")
    return {
        "receiptNo": receipt_no,
        "lineNo": line_no,
        "orderNo": _clean(raw.get("订单编号") or raw.get("orderNo")),
        "materialNumber": _clean(raw.get("料号") or raw.get("materialNumber")),
        "itemName": _clean(raw.get("料品名称") or raw.get("itemName")),
        "itemSpec": _clean(raw.get("料品规格") or raw.get("itemSpec")),
        "receivedQty": _clean(raw.get("实收数量") or raw.get("receivedQty")),
        "unitPrice": _clean(raw.get("单价（元）") or raw.get("单价(元)") or raw.get("unitPrice")),
        "untaxedUnitPrice": _clean(
            raw.get("未税单价（元）") or raw.get("未税单价") or raw.get("untaxedUnitPrice")
        ),
        "taxRate": _clean(raw.get("税率") or raw.get("taxRate")),
        "untaxedAmount": _clean(
            raw.get("可立账未税金额（元）") or raw.get("可立账未税金额") or raw.get("untaxedAmount")
        ).replace(",", ""),
        "taxAmount": _clean(
            raw.get("可立账税额（元）") or raw.get("可立账税额") or raw.get("taxAmount")
        ).replace(",", ""),
        "taxIncludedAmount": amount,
        "reconcileStatus": _clean(raw.get("对账状态") or raw.get("reconcileStatus")),
        "inboundConfirmDate": _clean(
            raw.get("入库确认日期")
            or raw.get("入库确认时间")
            or raw.get("inboundConfirmDate")
        ),
        "docDate": _clean(raw.get("单据日期") or raw.get("docDate")),
        "actualArrivalDate": _clean(
            raw.get("实际到货日期") or raw.get("actualArrivalDate")
        ),
        "docType": _clean(raw.get("单据类型") or raw.get("docType")),
        "billQty": _clean(raw.get("立账数量") or raw.get("billQty")),
        "supplierCode": _clean(raw.get("供应商编号") or raw.get("supplierCode")),
        "supplierName": _clean(raw.get("供应商名称") or raw.get("supplierName")),
    }


def normalize_receipt_rows(raw_rows):
    if not isinstance(raw_rows, list):
        raise RpaBusinessError(
            "SRM_STMT_RECEIPTS_INVALID",
            "Receipt list payload is invalid",
        )
    rows = []
    seen = set()
    for raw in raw_rows:
        row = normalize_receipt_row(raw)
        if row is None:
            continue
        if row.get("reconcileStatus") and row["reconcileStatus"] not in {
            UNSUBMITTED_STATUS,
            "未对账",
        }:
            continue
        key = (row["receiptNo"], row["lineNo"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


async def _safe_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
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
            captcha_now = self.page.locator(self.selector("captcha_image"))
            if await already.is_visible() and not await captcha_now.is_visible():
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
        success = self.page.locator(self.selector("login_success"))
        try:
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
            await _safe_screenshot(self.ctx, "stmt-receipts-captcha-unknown", step_id)
            raise RpaHumanRequiredError(
                "HUMAN_VERIFICATION_REQUIRED",
                "Supplier portal CAPTCHA requires human verification",
            )
        await self.page.fill(self.selector("username"), username)
        await self.page.fill(self.selector("password"), password)
        await self.page.fill(self.selector("captcha"), code)
        agreement = self.page.locator(self.selector("agreement"))
        if not await agreement.is_checked():
            await agreement.check()
        await self.page.click(self.selector("login_button"))
        success = self.page.locator(self.selector("login_success"))
        error = self.page.locator(self.selector("login_error"))
        for _ in range(50):
            if await success.is_visible():
                break
            if await error.is_visible():
                raise RpaBusinessError("SRM_LOGIN_FAILED", "Supplier portal login failed")
            await self.page.wait_for_timeout(200)
        else:
            raise RpaRetryableError("SRM_LOGIN_TIMEOUT", "Supplier portal login timeout")
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Supplier portal login completed",
            payload={"stepId": step_id},
        )

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
        await self._fill_date_range(date_start, date_end)
        await self.page.keyboard.press("Escape")
        await self.page.click(self.selector("search_button"))
        await self.page.wait_for_timeout(800)
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Receipt list opened",
            payload={"stepId": step_id},
        )

    async def _fill_date_range(self, date_start: str, date_end: str):
        box = self.page.locator(self.selector("date_range"))
        inputs = box.locator("input")
        if await inputs.count() < 2:
            raise RpaRetryableError(
                "SRM_STMT_DATE_RANGE_MISSING",
                "Receiving date range inputs are unavailable",
            )
        await self._fill_date_input(inputs.nth(0), date_start)
        await self._fill_date_input(inputs.nth(1), date_end)
        await self.page.keyboard.press("Enter")

    async def _fill_date_input(self, locator, value: str):
        await locator.click()
        try:
            await locator.fill(value)
        except Exception:
            await locator.evaluate(
                """(el, v) => {
                  el.removeAttribute('readonly');
                  el.value = v;
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                value,
            )

    async def collect_rows(self):
        all_rows = []
        for _ in range(MAX_PAGES):
            payload = await self.page.evaluate(COLLECT_RECEIPTS_JS)
            if not isinstance(payload, dict):
                break
            rows = payload.get("rows") or []
            all_rows.extend(rows)
            next_btn = self.page.locator(self.selector("next_page"))
            if not await next_btn.count() or await next_btn.is_disabled():
                break
            await next_btn.click()
            await self.page.wait_for_timeout(400)
        return all_rows


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")
    raw_input = ctx.input if isinstance(ctx.input, Mapping) else {}
    date_start = _clean(raw_input.get("dateStart") or raw_input.get("date_start"))
    date_end = _clean(raw_input.get("dateEnd") or raw_input.get("date_end"))
    if not date_start or not date_end:
        raise RpaFatalError("STMT_DATE_RANGE_REQUIRED", "dateStart/dateEnd are required")

    await ctx.log.info("Starting statement receipt query Flow")
    adapter = ReceiptListAdapter(ctx)
    await adapter.login()
    await adapter.open_receipt_list(date_start, date_end)
    raw_rows = await adapter.collect_rows()
    rows = normalize_receipt_rows(raw_rows)
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "portalUrl": ctx.portal_url,
        "dateStart": date_start,
        "dateEnd": date_end,
        "queriedAt": date.today().isoformat(),
        "totalRows": len(rows),
        "rows": rows,
    }
