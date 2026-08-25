"""SRM 对账单扫描发票（正式门户）。

输入：checkDate / checkAmount / filePaths
操作：对账列表 → 按日期+金额找未对账 → 收货应付 → 扫描发票并回写发票号/总额。
不点「提交审核」。提交由 submit_review 包再扫一次并核对后执行。
"""

import re
from collections.abc import Mapping
from pathlib import Path

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaRetryableError,
    login_official_srm,
)

OUTPUT_SCHEMA_VERSION = "SRM_STMT_UPLOAD_INVOICE_OUTPUT_V1"
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".ofd"}
UNCHECKED_STATUS = "未对账"
RECONCILE_STATUS_LABEL = "对账状态"
PAYABLE_BUTTON_TEXT = "收货应付"
STATEMENT_HASH = "#/reconciliation/reconciliationStatement"

FIND_STATEMENT_JS = r"""({checkDate, checkAmount}) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const normAmount = (value) => clean(value).replace(/,/g, '').replace(/[¥￥元]/g, '');
  const normDate = (value) => clean(value).replace(/\//g, '-').slice(0, 10);
  const wantDate = normDate(checkDate);
  const wantAmount = normAmount(checkAmount);
  const tables = [...document.querySelectorAll('.el-table')];
  if (!tables.length) return { error: 'table_missing' };
  const scored = tables.map((table) => {
    const headers = [...table.querySelectorAll('.el-table__header-wrapper th')]
      .map((th) => clean(th.innerText));
    const dateIdx = headers.findIndex((h) => h.includes('对账日期'));
    const amountIdx = headers.findIndex((h) => h.includes('对账总额') || h.includes('对账金额'));
    const rows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')];
    return { headers, dateIdx, amountIdx, rows };
  }).sort((a, b) => b.rows.length - a.rows.length);
  const picked = scored.find((item) => item.dateIdx >= 0 && item.amountIdx >= 0) || scored[0];
  if (picked.dateIdx < 0 || picked.amountIdx < 0) {
    return { error: 'columns_missing', headers: picked.headers };
  }
  const samples = picked.rows.slice(0, 5).map((tr) => {
    const cells = [...tr.querySelectorAll(':scope > td')].map((td) => clean(td.innerText));
    return { date: cells[picked.dateIdx] || '', amount: cells[picked.amountIdx] || '' };
  });
  for (let index = 0; index < picked.rows.length; index += 1) {
    const cells = [...picked.rows[index].querySelectorAll(':scope > td')]
      .map((td) => clean(td.innerText));
    const date = normDate(cells[picked.dateIdx] || '');
    const amount = normAmount(cells[picked.amountIdx] || '');
    if (date.startsWith(wantDate) && amount === wantAmount) {
      return {
        matched: true,
        rowIndex: index,
        date: cells[picked.dateIdx],
        amount: cells[picked.amountIdx],
      };
    }
  }
  return { error: 'not_found', samples, rowCount: picked.rows.length };
}"""

CLICK_PAYABLE_JS = r"""({ rowIndex, buttonText }) => {
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
  const rowSelector = '.el-table__body-wrapper tbody tr, .el-table__fixed-body-wrapper tbody tr';
  const tables = [...document.querySelectorAll('.el-table')];
  if (!tables.length) return 'no-table';
  const table = tables
    .map((candidate) => ({
      candidate,
      rowCount: candidate.querySelectorAll('.el-table__body-wrapper tbody tr').length,
    }))
    .sort((a, b) => b.rowCount - a.rowCount)[0].candidate;
  const sources = [
    table.querySelector('.el-table__fixed-right'),
    table.querySelector('.el-table__fixed'),
    table,
  ].filter(Boolean);
  for (const source of sources) {
    const rows = [...source.querySelectorAll(rowSelector)];
    const row = rows[rowIndex];
    if (!row) continue;
    const btn = [...row.querySelectorAll('button, a, span, .el-button, .el-link')].find((el) => {
      return isVisible(el) && String(el.innerText || '').includes(buttonText);
    });
    if (btn) {
      const target = btn.closest('button, a, .el-button, .el-link') || btn;
      target.click();
      return 'ok';
    }
  }
  return 'missing';
}"""

READ_BASE_INFO_JS = r"""() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const root = document.querySelector('.el-drawer:visible, .el-dialog:visible, .app-container, body');
  const STOP = '对账日期|对账状态|发票状态|对账总额|发票总额|发票金额|最后入库时间|对接业务员|对账业务员|发票号|发票号码|备注';
  const fromLabeled = (labelName) => {
    const labels = [...document.querySelectorAll('.el-form-item__label, .el-descriptions-item__label, label')];
    for (const labelEl of labels) {
      const label = clean(labelEl.innerText);
      if (label.indexOf(labelName) < 0) continue;
      if (labelName === '发票号' && /总额|金额|状态/.test(label)) continue;
      const item = labelEl.closest('.el-form-item, .el-descriptions-item');
      const content = item
        ? item.querySelector('.el-form-item__content, .el-descriptions-item__content')
        : labelEl.nextElementSibling;
      if (!content) continue;
      const nested = content.querySelector('input, textarea');
      if (nested && nested.value) return clean(nested.value);
      const clone = content.cloneNode(true);
      clone.querySelectorAll('textarea, input, .el-input__count, .el-textarea, .el-input')
        .forEach((n) => n.remove());
      const value = clean(clone.innerText);
      if (value) return value;
    }
    return '';
  };
  const pick = (name) => {
    const text = root ? String(root.innerText || '') : '';
    const match = text.match(new RegExp(name + '\\s*[:：]?\\s*([\\s\\S]*?)(?=\\s*(?:' + STOP + ')|$)'));
    return match ? clean(match[1]) : '';
  };
  return {
    invoiceNo: fromLabeled('发票号') || pick('发票号'),
    invoiceAmount: fromLabeled('发票总额') || fromLabeled('发票金额') || pick('发票总额'),
    checkStatus: fromLabeled('对账状态') || pick('对账状态'),
    invoiceStatus: fromLabeled('发票状态') || pick('发票状态'),
  };
}"""


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def normalize_invoice_no(raw):
    text = _clean(raw)
    if not text:
        return ""
    cut = len(text)
    for stop in ("备注", "请输入备注"):
        idx = text.find(stop)
        if idx >= 0:
            cut = min(cut, idx)
    text = _clean(text[:cut])
    text = re.sub(r"\s*\d+\s*/\s*\d+\s*$", "", text).strip()
    match = re.search(r"INV_[A-Z0-9]+", text, re.I)
    if match:
        return match.group(0)
    if re.fullmatch(r"\d+\s*/\s*\d+", text):
        return ""
    return text


def normalize_invoice_amount(raw):
    text = (
        _clean(raw)
        .replace(",", "")
        .replace("，", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("元", "")
    )
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def describe_not_found(check_date, check_amount, found):
    data = found if isinstance(found, dict) else {}
    samples = data.get("samples") or []
    preview = "；".join(
        f"{item.get('date')}/{item.get('amount')}"
        for item in samples[:3]
        if isinstance(item, dict)
    )
    extra = f"；列表样例 {preview}" if preview else "；列表为空或尚未查询"
    return f"对账列表未找到对账单：日期 {check_date}，金额 {check_amount}{extra}"


def require_match_key(raw_input):
    check_date = _clean(raw_input.get("checkDate") or raw_input.get("check_date"))
    check_amount = _clean(raw_input.get("checkAmount") or raw_input.get("check_amount"))
    if not check_date or not check_amount:
        raise RpaFatalError("STMT_MATCH_KEY_REQUIRED", "checkDate/checkAmount are required")
    return check_date, check_amount


def ensure_invoice_ready(invoice_no, invoice_amount):
    if not _clean(invoice_no):
        raise RpaBusinessError("STMT_INVOICE_NO_EMPTY", "invoice number is empty")
    if not _clean(invoice_amount) or _clean(invoice_amount).replace(",", "") in {"0", "0.00"}:
        raise RpaBusinessError("STMT_INVOICE_AMOUNT_EMPTY", "invoice amount is empty")


def validate_file_paths(raw_paths):
    if not isinstance(raw_paths, list) or not raw_paths:
        raise RpaFatalError("STMT_INVOICE_FILES_REQUIRED", "filePaths are required")
    if len(raw_paths) > 10:
        raise RpaFatalError("STMT_INVOICE_FILES_LIMIT", "at most 10 invoice files")
    paths = []
    for item in raw_paths:
        path = Path(_clean(item))
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise RpaFatalError("STMT_INVOICE_FILE_TYPE", f"unsupported invoice file type: {path.suffix}")
        paths.append(str(path))
    return paths


def upload_result(*, check_date, check_amount, invoice_no, invoice_amount, file_count):
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "checkDate": check_date,
        "checkAmount": check_amount,
        "invoiceNo": invoice_no,
        "invoiceAmount": invoice_amount,
        "uploadedFileCount": file_count,
        "checkStatus": "未对账",
        "invoiceStatus": "已扫描",
    }


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


class StatementSubmitAdapter:
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

    async def select_form_option(self, label, option):
        item = self.page.locator(".el-form-item").filter(
            has=self.page.locator(".el-form-item__label", has_text=label)
        ).first
        if await item.count() == 0:
            return False
        trigger = item.locator(".el-select input, .el-input__inner, input").first
        await trigger.click(timeout=4000)
        await self.page.wait_for_timeout(400)
        option_loc = self.page.locator(
            ".el-select-dropdown:visible li, .el-select-dropdown:visible .el-option"
        ).filter(has_text=option).first
        try:
            await option_loc.click(timeout=4000)
        except Exception:
            await self.page.keyboard.press("Escape")
            return False
        await self.page.wait_for_timeout(200)
        return True

    async def open_statement_list(self):
        step_id = "srm.open_statement_list"
        await _safe_emit(
            self.ctx,
            "STEP_STARTED",
            message="Opening statement list",
            payload={"stepId": step_id, "stepType": step_id},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        await self.page.goto(
            f"{portal_root}/{STATEMENT_HASH}", wait_until="domcontentloaded"
        )
        page = self.page.locator(self.selector("statement_page"))
        try:
            await page.wait_for(state="visible", timeout=15000)
        except Exception as exc:
            await _safe_screenshot(self.ctx, "stmt-list-missing", step_id)
            raise RpaBusinessError(
                "SRM_STMT_LIST_PAGE_MISSING",
                "Statement list page is unavailable",
            ) from exc
        await self.select_form_option(RECONCILE_STATUS_LABEL, UNCHECKED_STATUS)
        await self.page.locator(self.selector("search_button")).click(timeout=4000)
        await self._wait_loading_done()
        await self.page.wait_for_timeout(500)
        await _safe_emit(
            self.ctx,
            "STEP_SUCCEEDED",
            message="Statement list opened",
            payload={"stepId": step_id},
        )

    async def _find_on_pages(self, check_date, check_amount):
        last = {"error": "not_found"}
        for _ in range(20):
            found = await self.page.evaluate(
                FIND_STATEMENT_JS, {"checkDate": check_date, "checkAmount": check_amount}
            )
            if isinstance(found, dict) and found.get("matched") and found.get("rowIndex") is not None:
                return found
            if isinstance(found, dict):
                last = found
            next_btn = self.page.locator(self.selector("next_page")).first
            if not await next_btn.count():
                return last
            try:
                if await next_btn.is_disabled():
                    return last
            except Exception:
                return last
            await next_btn.click()
            await self.page.wait_for_timeout(500)
            await self._wait_loading_done()
        return last

    async def _click_visible_payable(self, row_index):
        locators = [
            self.page.locator(".el-table__fixed-right tbody tr").nth(row_index).get_by_text(
                PAYABLE_BUTTON_TEXT
            ),
            self.page.locator(".el-table__fixed tbody tr").nth(row_index).get_by_text(
                PAYABLE_BUTTON_TEXT
            ),
            self.page.locator(".el-table__body-wrapper tbody tr").nth(row_index).get_by_text(
                PAYABLE_BUTTON_TEXT
            ),
        ]
        for loc in locators:
            try:
                visible = loc.locator("visible=true")
                if await visible.count():
                    await visible.first.click(timeout=4000)
                    return True
            except Exception:
                continue
        return False

    async def open_payable(self, check_date, check_amount):
        step_id = "srm.open_payable"
        await _safe_emit(
            self.ctx,
            "STEP_STARTED",
            message="Opening unpaid statement payable detail",
            payload={"stepId": step_id, "stepType": step_id},
        )
        found = await self._find_on_pages(check_date, check_amount)
        if not isinstance(found, dict) or not found.get("matched"):
            await _safe_screenshot(self.ctx, "stmt-not-found", step_id)
            raise RpaBusinessError(
                "SRM_STMT_NOT_FOUND",
                describe_not_found(check_date, check_amount, found),
            )
        matched_date = found.get("date") or check_date
        matched_amount = found.get("amount") or check_amount
        await _safe_emit(
            self.ctx,
            "STEP_STARTED",
            message=f"Matched statement {matched_date} / {matched_amount}",
            payload={
                "stepId": step_id,
                "rowIndex": found.get("rowIndex"),
                "matchedDate": matched_date,
                "matchedAmount": matched_amount,
                "wantDate": check_date,
                "wantAmount": check_amount,
            },
        )
        result = await self.page.evaluate(
            CLICK_PAYABLE_JS,
            {"rowIndex": int(found["rowIndex"]), "buttonText": PAYABLE_BUTTON_TEXT},
        )
        if result != "ok":
            if await self._click_visible_payable(int(found["rowIndex"])):
                result = "ok"
        if result != "ok":
            await _safe_screenshot(self.ctx, "stmt-payable-unclickable", step_id)
            raise RpaRetryableError(
                "SRM_STMT_PAYABLE_UNCLICKABLE",
                f"匹配到 {matched_date} / {matched_amount} 后，收货应付按钮不可点击（{result}）",
            )
        payable = self.page.locator(self.selector("payable_page")).first
        try:
            await payable.wait_for(state="visible", timeout=15000)
        except Exception as exc:
            await _safe_screenshot(self.ctx, "stmt-payable-missing", step_id)
            raise RpaBusinessError(
                "SRM_STMT_PAYABLE_PAGE_MISSING",
                "Payable detail is unavailable",
            ) from exc
        await _safe_screenshot(self.ctx, "stmt-payable-detail", step_id)
        await _safe_emit(
            self.ctx,
            "STEP_SUCCEEDED",
            message="Payable detail opened",
            payload={"stepId": step_id, "rowIndex": found.get("rowIndex")},
        )

    async def scan_invoices(self, file_paths):
        step_id = "srm.upload_invoice"
        await _safe_emit(
            self.ctx,
            "STEP_STARTED",
            message="Scanning invoice files",
            payload={"stepId": step_id, "stepType": step_id, "fileCount": len(file_paths)},
        )
        scan = self.page.locator(self.selector("scan_button")).first
        try:
            await scan.wait_for(state="visible", timeout=8000)
            await scan.click(timeout=4000)
        except Exception as exc:
            await _safe_screenshot(self.ctx, "stmt-scan-button-missing", step_id)
            raise RpaRetryableError(
                "SRM_STMT_SCAN_BUTTON_MISSING",
                "Scan invoice button is unavailable",
            ) from exc
        file_input = self.page.locator(self.selector("file_input"))
        try:
            await file_input.first.wait_for(state="attached", timeout=8000)
            await file_input.first.set_input_files(file_paths)
        except Exception as exc:
            await _safe_screenshot(self.ctx, "stmt-invoice-input-missing", step_id)
            raise RpaRetryableError(
                "SRM_STMT_INVOICE_INPUT_MISSING",
                "invoice file input missing",
            ) from exc
        confirm = self.page.locator(self.selector("upload_confirm"))
        if await confirm.count():
            try:
                await confirm.first.click(timeout=4000)
            except Exception:
                pass
        invoice_no = ""
        invoice_amount = ""
        for _ in range(30):
            info = await self.page.evaluate(READ_BASE_INFO_JS)
            invoice_no = normalize_invoice_no((info or {}).get("invoiceNo"))
            invoice_amount = normalize_invoice_amount((info or {}).get("invoiceAmount"))
            if invoice_no and invoice_amount and invoice_amount not in {"0", "0.00"}:
                await _safe_screenshot(self.ctx, "stmt-invoice-scanned", step_id)
                await _safe_emit(
                    self.ctx,
                    "STEP_SUCCEEDED",
                    message="Invoice scanned",
                    payload={"stepId": step_id, "invoiceNo": invoice_no},
                )
                return invoice_no, invoice_amount
            await self.page.wait_for_timeout(1000)
        await _safe_screenshot(self.ctx, "stmt-invoice-ocr-empty", step_id)
        if not invoice_no:
            raise RpaBusinessError("STMT_INVOICE_OCR_EMPTY", "SRM did not write back invoice number")
        raise RpaBusinessError("STMT_INVOICE_AMOUNT_EMPTY", "SRM did not write back invoice amount")

    async def locate_submit_button(self):
        button = self.page.locator(self.selector("submit_button")).first
        try:
            await button.wait_for(state="visible", timeout=8000)
        except Exception as exc:
            await _safe_screenshot(self.ctx, "stmt-submit-button-missing", "srm.submit_review")
            raise RpaBusinessError(
                "SRM_STMT_SUBMIT_BUTTON_MISSING",
                "Submit review button is not visible",
            ) from exc
        disabled = False
        try:
            disabled = await button.is_disabled()
        except Exception:
            disabled = False
        classes = _clean(await button.get_attribute("class"))
        if disabled or "is-disabled" in classes:
            await _safe_screenshot(self.ctx, "stmt-submit-button-disabled", "srm.submit_review")
            raise RpaBusinessError(
                "SRM_STMT_SUBMIT_BUTTON_DISABLED",
                "Submit review button is visible but disabled",
            )
        return button

    async def click_submit(self, button):
        await button.click(timeout=4000)
        toast = self.page.locator(self.selector("success_toast"))
        try:
            await toast.first.wait_for(state="visible", timeout=15000)
        except Exception:
            await _safe_screenshot(self.ctx, "stmt-submit-no-toast", "srm.submit_review")
            error = self.page.locator(".el-message--error")
            if await error.count():
                raise RpaBusinessError(
                    "SRM_STMT_SUBMIT_FAILED",
                    await error.first.inner_text(),
                )
            raise RpaRetryableError(
                "SRM_STMT_SUBMIT_UNCONFIRMED",
                "submit result toast missing",
            )


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")
    raw_input = ctx.input if isinstance(ctx.input, Mapping) else {}
    check_date, check_amount = require_match_key(raw_input)
    file_paths = validate_file_paths(raw_input.get("filePaths") or raw_input.get("file_paths"))

    await ctx.log.info("Starting statement upload invoice Flow")
    adapter = StatementSubmitAdapter(ctx)
    await adapter.login()
    await adapter.open_statement_list()
    await adapter.open_payable(check_date, check_amount)

    step_id = "srm.upload_invoice"
    await _safe_emit(
        ctx,
        "STEP_STARTED",
        message="Scanning invoice files",
        payload={"stepId": step_id, "stepType": step_id},
    )
    invoice_no, invoice_amount = await adapter.scan_invoices(file_paths)
    ensure_invoice_ready(invoice_no, invoice_amount)
    await _safe_screenshot(ctx, "stmt-invoice-scanned", step_id)
    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Invoice scanned",
        payload={"stepId": step_id, "invoiceNo": invoice_no},
    )
    return upload_result(
        check_date=check_date,
        check_amount=check_amount,
        invoice_no=invoice_no,
        invoice_amount=invoice_amount,
        file_count=len(file_paths),
    )
