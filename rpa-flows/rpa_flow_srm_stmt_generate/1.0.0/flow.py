"""SRM 生成对账单。

输入：lines[{receiptNo,lineNo,orderNo?}], dateStart/dateEnd, localAmount
输出：{ schemaVersion, checkDate, checkAmount }
"""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

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
OUTPUT_SCHEMA_VERSION = "SRM_STMT_GENERATE_OUTPUT_V1"
COLLECT_ROWS_JS = r"""() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const page = document.querySelector("[data-rpa='receiving-list-page']");
  if (!page) return [];
  const table = [...page.querySelectorAll('.el-table')].sort(
    (a, b) => b.querySelectorAll('tbody tr').length - a.querySelectorAll('tbody tr').length
  )[0];
  if (!table) return [];
  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.innerText));
  return [...table.querySelectorAll('.el-table__body-wrapper tbody tr')].map((tr) => {
    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
    const row = {};
    headers.forEach((header, index) => { if (header) row[header] = cells[index] || ''; });
    row._rpa = tr.getAttribute('data-rpa') || [...tr.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa'))[0] || '';
    return row;
  });
}"""


def _clean(value):
    return str(value or "").strip()


def resolve_captcha_code(src):
    text = _clean(src).lower()
    for key, code in CAPTCHA_CODES.items():
        if key in text:
            return code
    return None


def parse_lines(raw_lines):
    if not isinstance(raw_lines, list) or not raw_lines:
        raise RpaFatalError("STMT_LINES_REQUIRED", "lines are required")
    lines = []
    for item in raw_lines:
        if not isinstance(item, Mapping):
            continue
        receipt_no = _clean(item.get("receiptNo") or item.get("receipt_no") or item.get("收货单号"))
        line_no = _clean(item.get("lineNo") or item.get("line_no") or item.get("收货单行号") or item.get("行号"))
        order_no = _clean(item.get("orderNo") or item.get("order_no") or item.get("订单编号"))
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


async def _safe_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return


class StatementGenerateAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.page
        self.selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}

    def selector(self, name, **values):
        value = self.selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError("FLOW_SELECTOR_MISSING", f"missing selector: {name}")
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    async def _session_already_authenticated(self):
        try:
            already = self.page.locator(self.selector("login_success"))
            captcha = self.page.locator(self.selector("captcha_image"))
            return await already.is_visible() and not await captcha.is_visible()
        except Exception:
            return False

    async def login(self):
        credentials = self.ctx.credentials if isinstance(self.ctx.credentials, Mapping) else {}
        username = _clean(credentials.get("username"))
        password = str(credentials.get("password", ""))
        if not username or not password:
            raise RpaFatalError("SRM_CREDENTIALS_MISSING", "Supplier portal credentials are unavailable")
        # Runtime 重试复用同一 browser context；已登录则不要再等验证码。
        if await self._session_already_authenticated():
            return
        await self.page.goto(self.ctx.portal_url, wait_until="domcontentloaded")
        captcha = self.page.locator(self.selector("captcha_image"))
        success = self.page.locator(self.selector("login_success"))
        try:
            for _ in range(50):
                if await captcha.is_visible():
                    break
                if await success.is_visible() and not await captcha.is_visible():
                    return
                await self.page.wait_for_timeout(200)
            else:
                await captcha.wait_for(state="visible", timeout=1000)
            code = resolve_captcha_code(await captcha.get_attribute("src"))
        except Exception as exc:
            raise RpaRetryableError("SRM_LOGIN_PAGE_UNAVAILABLE", "login page unavailable") from exc
        if code is None:
            raise RpaHumanRequiredError("HUMAN_VERIFICATION_REQUIRED", "CAPTCHA requires human")
        await self.page.fill(self.selector("username"), username)
        await self.page.fill(self.selector("password"), password)
        await self.page.fill(self.selector("captcha"), code)
        agreement = self.page.locator(self.selector("agreement"))
        if not await agreement.is_checked():
            await agreement.check()
        await self.page.click(self.selector("login_button"))
        error = self.page.locator(self.selector("login_error"))
        for _ in range(50):
            if await success.is_visible():
                return
            if await error.is_visible():
                raise RpaBusinessError("SRM_LOGIN_FAILED", "login failed")
            await self.page.wait_for_timeout(200)
        raise RpaRetryableError("SRM_LOGIN_TIMEOUT", "login timeout")

    async def open_receipt_list(self, date_start, date_end):
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        await self.page.goto(f"{portal_root}/#/supplier/receivings", wait_until="domcontentloaded")
        await self.page.locator(self.selector("receipt_page")).wait_for(state="visible", timeout=15000)
        if date_start and date_end:
            box = self.page.locator(self.selector("date_range"))
            inputs = box.locator("input")
            await inputs.nth(0).click()
            await inputs.nth(0).fill(date_start)
            await inputs.nth(1).click()
            await inputs.nth(1).fill(date_end)
            await self.page.keyboard.press("Enter")
            await self.page.click(self.selector("search_button"))
            await self.page.wait_for_timeout(800)

    def _row_locator(self, order_no, line_no):
        marker = self.page.locator(self.selector("row_marker", orderNo=order_no, lineNo=line_no))
        return self.page.locator(".el-table__body-wrapper tbody tr").filter(has=marker).first

    async def select_lines(self, lines):
        raw_rows = await self.page.evaluate(COLLECT_ROWS_JS)
        by_receipt = {}
        for row in raw_rows if isinstance(raw_rows, list) else []:
            line_no = _clean(row.get("收货单行号") or row.get("行号") or row.get("lineNo"))
            receipt_no = _clean(row.get("收货单号") or row.get("receiptNo"))
            if receipt_no and line_no:
                by_receipt[(receipt_no, line_no)] = row
        missing = []
        for line in lines:
            row = by_receipt.get((line["receiptNo"], line["lineNo"]))
            order_no = line.get("orderNo") or _clean((row or {}).get("订单编号"))
            if not order_no:
                missing.append(f"{line['receiptNo']}/{line['lineNo']}")
                continue
            locator = self._row_locator(order_no, line["lineNo"])
            if not await locator.count():
                missing.append(f"{line['receiptNo']}/{line['lineNo']}")
                continue
            await self._check_row(locator)
        if missing:
            raise RpaBusinessError(
                "SRM_STMT_GENERATE_MISMATCH",
                f"receipt lines not found on page: {', '.join(missing[:8])}",
            )

    async def _check_row(self, row):
        checkbox = row.locator("td.el-table-column--selection .el-checkbox").first
        try:
            await checkbox.click(timeout=10000)
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_STMT_ROW_CHECKBOX_UNCLICKABLE",
                "receipt row checkbox is not clickable",
            ) from exc

    async def click_generate(self):
        await self.page.click(self.selector("generate_button"))
        toast = self.page.locator(self.selector("success_toast"))
        try:
            await toast.first.wait_for(state="visible", timeout=15000)
        except Exception:
            await _safe_screenshot(self.ctx, "stmt-generate-no-toast", "srm.generate")
            error = self.page.locator(".el-message--error")
            if await error.count():
                raise RpaBusinessError("SRM_STMT_GENERATE_FAILED", await error.first.inner_text())
            raise RpaRetryableError("SRM_STMT_GENERATE_UNCONFIRMED", "generate result toast missing")


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")
    raw_input = ctx.input if isinstance(ctx.input, Mapping) else {}
    lines = parse_lines(raw_input.get("lines"))
    check_amount = resolve_check_amount(raw_input, raw_input.get("lines"))
    check_date = date.today().isoformat()
    adapter = StatementGenerateAdapter(ctx)
    await adapter.login()
    await adapter.open_receipt_list(
        _clean(raw_input.get("dateStart") or raw_input.get("date_start")),
        _clean(raw_input.get("dateEnd") or raw_input.get("date_end")),
    )
    await adapter.select_lines(lines)
    await adapter.click_generate()
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "checkDate": check_date,
        "checkAmount": check_amount,
        "selectedLineCount": len(lines),
    }
