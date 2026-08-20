"""SRM 对账单提交审核。"""

import re
from collections.abc import Mapping
from pathlib import Path

from nodeskclaw_rpa_engine.runtime import (
    login_official_srm,
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
OUTPUT_SCHEMA_VERSION = "SRM_STMT_SUBMIT_REVIEW_OUTPUT_V1"
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".ofd"}
FIND_STATEMENT_JS = r"""({checkDate, checkAmount}) => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const normAmount = (value) => clean(value).replace(/,/g, '').replace(/[¥￥元]/g, '');
  const normDate = (value) => clean(value).replace(/\//g, '-');
  const page = document.querySelector("[data-rpa='reconciliation-page']");
  if (!page) return { error: 'page_missing' };
  const table = page.querySelector("[data-rpa='reconciliation-table'] .el-table, .el-table");
  if (!table) return { error: 'table_missing' };
  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.innerText));
  const dateIdx = headers.findIndex((h) => h.includes('对账日期'));
  const amountIdx = headers.findIndex((h) => h.includes('对账总额'));
  const rows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')];
  const samples = rows.slice(0, 5).map((tr) => {
    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
    return { date: cells[dateIdx] || '', amount: cells[amountIdx] || '' };
  });
  if (dateIdx < 0 || amountIdx < 0) return { error: 'columns_missing', headers, samples };
  const wantDate = normDate(checkDate);
  const wantAmount = normAmount(checkAmount);
  for (const tr of rows) {
    const cells = [...tr.querySelectorAll('td')].map((td) => clean(td.innerText));
    if (normDate(cells[dateIdx] || '').startsWith(wantDate) && normAmount(cells[amountIdx] || '') === wantAmount) {
      const payable = [...tr.querySelectorAll('[data-rpa^="reconciliation-payable-"]')]
        .map((el) => el.getAttribute('data-rpa'))[0];
      return { rpa: payable || null, matched: true };
    }
  }
  return { error: 'not_found', samples, rowCount: rows.length };
}"""
READ_BASE_INFO_JS = r"""() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const root = document.querySelector("[data-rpa='payable-base-info']") || document.querySelector("[data-rpa='payable-page']");
  const STOP = '对账日期|对账状态|发票状态|对账总额|发票总额|发票金额|最后入库时间|对接业务员|对账业务员|发票号|发票号码|备注';
  const byRpa = (key) => {
    const el = document.querySelector("[data-rpa='" + key + "']");
    if (!el) return '';
    if (el.matches('input, textarea')) return clean(el.value);
    const nested = el.querySelector('input, textarea');
    if (nested) return clean(nested.value);
    return clean(el.innerText);
  };
  const fromLabeled = (labelName) => {
    const labels = [...(root || document).querySelectorAll('.el-form-item__label, .el-descriptions-item__label, label')];
    for (const labelEl of labels) {
      const label = clean(labelEl.innerText);
      if (label.indexOf(labelName) < 0) continue;
      if (labelName === '发票号' && /总额|金额|状态/.test(label)) continue;
      const item = labelEl.closest('.el-form-item, .el-descriptions-item');
      const content = item
        ? item.querySelector('.el-form-item__content, .el-descriptions-item__content')
        : labelEl.nextElementSibling;
      if (!content) continue;
      const clone = content.cloneNode(true);
      clone.querySelectorAll('textarea, input, .el-input__count, .el-textarea, .el-input').forEach((n) => n.remove());
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
    invoiceNo: byRpa('payable-invoice-no') || fromLabeled('发票号') || pick('发票号'),
    invoiceAmount: byRpa('payable-invoice-amount') || fromLabeled('发票总额') || fromLabeled('发票金额') || pick('发票总额'),
    checkStatus: fromLabeled('对账状态') || pick('对账状态'),
    invoiceStatus: fromLabeled('发票状态') || pick('发票状态'),
  };
}"""


def _clean(value):
    return str(value or "").strip()


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


def resolve_captcha_code(src):
    text = _clean(src).lower()
    for key, code in CAPTCHA_CODES.items():
        if key in text:
            return code
    return None


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


async def _login(ctx):
    selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}

    def selector(name, **values):
        value = selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError("FLOW_SELECTOR_MISSING", f"missing selector: {name}")
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    await login_official_srm(ctx, selector=selector)

async def _wait_loading(page, selectors):
    mask = page.locator(selectors.get("loading_mask") or ".el-loading-mask")
    try:
        await mask.first.wait_for(state="hidden", timeout=8000)
    except Exception:
        return


async def _click_search(page, selectors):
    await page.click(selectors["search_button"])
    await page.wait_for_timeout(800)
    await _wait_loading(page, selectors)


async def _click_payable(page, rpa_attr):
    marker = f"[data-rpa='{rpa_attr}']"
    preferred = page.locator(f".el-table__fixed-right {marker}").first
    try:
        if await preferred.count() and await preferred.is_visible():
            await preferred.click(timeout=8000)
            return
    except Exception:
        pass
    fallback = page.locator(marker)
    count = await fallback.count()
    for index in range(count - 1, -1, -1):
        loc = fallback.nth(index)
        try:
            if await loc.is_visible():
                await loc.click(timeout=8000)
                return
        except Exception:
            continue
    raise RpaRetryableError(
        "SRM_STMT_PAYABLE_UNCLICKABLE",
        "匹配到对账单后，收货应付按钮不可点击",
    )


async def _find_on_pages(page, selectors, check_date, check_amount):
    last = {"error": "not_found"}
    for _ in range(20):
        found = await page.evaluate(
            FIND_STATEMENT_JS, {"checkDate": check_date, "checkAmount": check_amount}
        )
        if isinstance(found, dict) and found.get("rpa"):
            return found
        if isinstance(found, dict):
            last = found
        next_btn = page.locator(selectors.get("next_page") or ".el-pagination .btn-next")
        if not await next_btn.count() or await next_btn.is_disabled():
            return last
        await next_btn.click()
        await page.wait_for_timeout(500)
        await _wait_loading(page, selectors)
    return last


async def _open_payable(ctx, check_date, check_amount):
    selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}
    page = ctx.page
    portal_root = ctx.portal_url.split("#", 1)[0].rstrip("/")
    await page.goto(f"{portal_root}/#/finance/reconciliation", wait_until="domcontentloaded")
    await page.locator(selectors["statement_page"]).wait_for(state="visible", timeout=15000)
    await _click_search(page, selectors)
    found = await _find_on_pages(page, selectors, check_date, check_amount)
    if not isinstance(found, dict) or not found.get("rpa"):
        raise RpaBusinessError("SRM_STMT_NOT_FOUND", describe_not_found(check_date, check_amount, found))
    await _click_payable(page, found["rpa"])
    await page.locator(selectors["payable_page"]).wait_for(state="visible", timeout=15000)


async def _scan_invoices(page, selectors, file_paths):
    await page.click(selectors["scan_button"])
    file_input = page.locator(selectors["file_input"])
    try:
        await file_input.first.wait_for(state="attached", timeout=8000)
        await file_input.first.set_input_files(file_paths)
    except Exception as exc:
        raise RpaRetryableError("SRM_STMT_INVOICE_INPUT_MISSING", "invoice file input missing") from exc
    if selectors.get("upload_confirm"):
        confirm = page.locator(selectors["upload_confirm"])
        if await confirm.count():
            await confirm.first.click()
    invoice_no = ""
    invoice_amount = ""
    for _ in range(30):
        info = await page.evaluate(READ_BASE_INFO_JS)
        invoice_no = normalize_invoice_no((info or {}).get("invoiceNo"))
        invoice_amount = normalize_invoice_amount((info or {}).get("invoiceAmount"))
        if invoice_no and invoice_amount and invoice_amount not in {"0", "0.00"}:
            return invoice_no, invoice_amount
        await page.wait_for_timeout(1000)
    if not invoice_no:
        raise RpaBusinessError("STMT_INVOICE_OCR_EMPTY", "SRM did not write back invoice number")
    raise RpaBusinessError("STMT_INVOICE_AMOUNT_EMPTY", "SRM did not write back invoice amount")


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError("PORTAL_URL_MISSING", "Supplier portal URL is unavailable")
    raw_input = ctx.input if isinstance(ctx.input, Mapping) else {}
    check_date, check_amount = require_match_key(raw_input)
    file_paths = validate_file_paths(raw_input.get("filePaths") or raw_input.get("file_paths"))
    selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}
    await _login(ctx)
    await _open_payable(ctx, check_date, check_amount)
    page = ctx.page
    invoice_no, invoice_amount = await _scan_invoices(page, selectors, file_paths)
    ensure_invoice_ready(invoice_no, invoice_amount)
    await page.click(selectors["submit_button"])
    await page.wait_for_timeout(1200)
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "checkDate": check_date,
        "checkAmount": check_amount,
        "invoiceNo": invoice_no,
        "invoiceAmount": invoice_amount,
        "checkStatus": "已对账",
        "invoiceStatus": "审核中",
        "uploadedFileCount": len(file_paths),
    }
