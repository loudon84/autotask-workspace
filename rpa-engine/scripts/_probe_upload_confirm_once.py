"""One-off: reproduce the 确定 (upload confirm) click timeout on official SRM.

Read-only-ish: uploads the real invoice PDF into the scan dialog and probes the
确定 button. 提交审核 / 保存 URLs are aborted by the write guard. Never clicks 提交审核.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"),
)

SCRIPTS = Path(__file__).resolve().parent
ENGINE_ROOT = SCRIPTS.parent
sys.path.insert(0, str(ENGINE_ROOT / "src"))
sys.path.insert(0, str(SCRIPTS))

from nodeskclaw_rpa_engine.runtime.actionability import inspect_clickable
from nodeskclaw_rpa_engine.runtime.captcha_ocr import get_classifier, parse_ocr_prediction
from playwright.async_api import async_playwright

import probe_official_stmt_payable_click as base
import probe_tiandy_prod_readonly as probe

OUT_DIR = ENGINE_ROOT / "runtime-cache" / "upload-confirm-probe"
OUT_JSON = OUT_DIR / "result.json"
INVOICE_PDF = ENGINE_ROOT / "runtime-cache" / "invoice-sample.pdf"
STATEMENT_HASH = "#/reconciliation/reconciliationStatement"

SEL_USER = "input[placeholder='账号或手机号码']:visible"
SEL_PASS = "input[type='password']:visible"
SEL_CAPTCHA = "input[placeholder='验证码']:visible"
SEL_CAPTCHA_IMG = ".el-form-item:has(input[placeholder='验证码']) img:visible"
SEL_LOGIN_BTN = "button:has-text('登录'):visible"
SEL_SUCCESS = ".el-menu-item:has-text('订单'):visible, span:has-text('订单'):visible"
CONFIRM_SEL = (
    ".el-dialog:visible .el-dialog__footer button:has-text('确定'):visible, "
    ".el-dialog:visible button.el-button--primary:has-text('确定'):visible, "
    ".el-message-box:visible button:has-text('确定'):visible, "
    ".el-dialog:visible button:has-text('确认'):visible"
)

DIALOG_DUMP_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const isVisible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return false;
    const style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  };
  const dialogs = [...document.querySelectorAll('.el-dialog, .el-message-box, .el-drawer')]
    .filter(isVisible)
    .map((dialog) => ({
      title: clean(dialog.querySelector('.el-dialog__title, .el-message-box__title, .el-drawer__header')?.innerText),
      buttons: [...dialog.querySelectorAll('button, .el-button')].map((btn) => ({
        text: clean(btn.innerText),
        disabled: !!(btn.disabled || String(btn.className || '').includes('is-disabled')),
        className: String(btn.className || '').slice(0, 100),
      })).filter((b) => b.text),
      fileInputs: dialog.querySelectorAll('input[type="file"]').length,
      bodyText: clean(dialog.querySelector('.el-dialog__body')?.innerText).slice(0, 300),
    }));
  const overlays = [...document.querySelectorAll('.el-message, .el-loading-mask, .v-modal')]
    .filter(isVisible)
    .map((el) => ({
      cls: String(el.className || '').slice(0, 80),
      text: clean(el.innerText).slice(0, 80),
      zIndex: window.getComputedStyle(el).zIndex,
    }));
  return { dialogs, overlays };
}"""


async def login(page, username: str, password: str) -> dict:
    engine = get_classifier()
    await page.goto("https://supplier.tiandy.com", wait_until="domcontentloaded")
    await page.wait_for_timeout(2500)
    await page.fill(SEL_USER, username)
    await page.fill(SEL_PASS, password)
    agreement = page.locator(".userAgree .el-checkbox:visible").first
    if await agreement.count():
        cls = (await agreement.get_attribute("class")) or ""
        if "is-checked" not in cls:
            await agreement.evaluate("el => (el.querySelector('.el-checkbox__inner') || el).click()")
    for attempt in range(1, 7):
        img = page.locator(SEL_CAPTCHA_IMG).first
        shot = await img.screenshot(type="png", timeout=5000)
        try:
            prediction = engine.classification(shot, probability=True)
        except TypeError:
            prediction = engine.classification(shot)
        ocr = parse_ocr_prediction(prediction)
        if not ocr.accepted:
            await img.click()
            await page.wait_for_timeout(900)
            continue
        await page.fill(SEL_CAPTCHA, ocr.text)
        await page.click(SEL_LOGIN_BTN, timeout=8000)
        try:
            await page.locator(SEL_SUCCESS).first.wait_for(state="visible", timeout=10000)
            return {"ok": True, "attempt": attempt}
        except Exception:
            err = page.locator(".el-message--error").first
            text = (await err.inner_text()).strip() if await err.count() else ""
            if "验证码" not in text:
                return {"ok": False, "error": text}
            await page.wait_for_timeout(900)
    return {"ok": False, "error": "captcha attempts exhausted"}


async def shot(page, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=True)


async def main() -> int:
    check_date = os.environ.get("PROBE_CHECK_DATE", "2026-10-09")
    check_amount = os.environ.get("PROBE_CHECK_AMOUNT", "3354661.32")
    probe.load_env_file(probe.ENV_FILE)
    username = os.environ.get("SUPPLIER_PORTAL_USERNAME", "").strip()
    password = os.environ.get("SUPPLIER_PORTAL_PASSWORD", "")
    if not username or not password:
        print("missing credentials")
        return 2
    if not INVOICE_PDF.is_file():
        print("invoice sample missing:", INVOICE_PDF)
        return 2
    flow = base.load_flow()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result: dict = {"at": datetime.now(UTC).isoformat(), "checkDate": check_date, "checkAmount": check_amount}

    async with async_playwright() as pw:
        browser, context, page, label = await probe.launch_browser(pw, headless=True)
        result["browser"] = label

        async def on_route(route):
            request = route.request
            if probe.should_block_probe_write(request.method, request.url):
                result.setdefault("blockedWrites", []).append(request.url[:120])
                await route.abort("blockedbyclient")
                return
            await route.continue_()

        await page.route("**/*", on_route)

        from nodeskclaw_rpa_engine.runtime.session_cache import session_cache_key

        state_path = (
            ENGINE_ROOT
            / "runtime-cache"
            / "sessions"
            / session_cache_key("https://supplier.tiandy.com", username)
            / "storage_state.json"
        )
        reused = False
        if state_path.is_file():
            await context.close()
            context = await browser.new_context(
                viewport={"width": 1600, "height": 1000}, storage_state=str(state_path)
            )
            page = await context.new_page()
            await page.route("**/*", on_route)
            await page.goto("https://supplier.tiandy.com", wait_until="domcontentloaded")
            try:
                await page.locator(SEL_SUCCESS).first.wait_for(state="visible", timeout=8000)
                reused = True
            except Exception:
                reused = False
        if reused:
            result["login"] = {"ok": True, "reusedSession": True}
        else:
            result["login"] = await login(page, username, password)
        print("login", json.dumps(result["login"], ensure_ascii=False), flush=True)
        if not result["login"].get("ok"):
            await shot(page, "login-failed")
            OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            await browser.close()
            return 3
        if not reused:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(state_path))
            result["sessionSaved"] = str(state_path)

        portal_root = "https://supplier.tiandy.com"
        await page.goto(f"{portal_root}/{STATEMENT_HASH}", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        await probe.select_form_option(page, "对账状态", "未对账")
        await page.locator("button:has-text('查询'):visible").click(timeout=4000)
        await page.wait_for_timeout(1500)

        found = await page.evaluate(flow.FIND_STATEMENT_JS, {"checkDate": check_date, "checkAmount": check_amount})
        result["find"] = found
        print("find", json.dumps(found, ensure_ascii=False), flush=True)
        if not found.get("matched"):
            await shot(page, "not-found")
            OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            await browser.close()
            return 2
        click = await page.evaluate(flow.CLICK_PAYABLE_JS, {"rowIndex": int(found["rowIndex"]), "buttonText": "收货应付"})
        result["click"] = click
        await page.wait_for_timeout(2000)
        await shot(page, "01-payable")

        scan = page.locator("button:has-text('扫描发票信息'):visible, button:has-text('扫描发票'):visible").first
        await scan.click(timeout=5000)
        await page.wait_for_timeout(1500)
        await shot(page, "02-scan-dialog")
        result["dialogBeforeUpload"] = await page.evaluate(DIALOG_DUMP_JS)

        file_input = page.locator(".el-dialog:visible input[type='file']").first
        await file_input.set_input_files(str(INVOICE_PDF))
        await page.wait_for_timeout(1000)
        # wait for upload to settle: success toast or file row appears
        await page.wait_for_timeout(3000)
        await shot(page, "03-after-upload")
        result["dialogAfterUpload"] = await page.evaluate(DIALOG_DUMP_JS)
        print("afterUpload", json.dumps(result["dialogAfterUpload"], ensure_ascii=False), flush=True)

        confirm = page.locator(CONFIRM_SEL).first
        result["confirmVisible"] = await confirm.count() > 0
        if result["confirmVisible"]:
            result["confirmInspect"] = await inspect_clickable(confirm)
            print("confirmInspect", json.dumps(result["confirmInspect"], ensure_ascii=False), flush=True)
            try:
                await confirm.click(timeout=4000)
                result["confirmClick"] = "ok"
            except Exception as exc:
                result["confirmClick"] = f"timeout: {type(exc).__name__}"
                result["confirmInspectAfterFail"] = await inspect_clickable(confirm)
                await shot(page, "04-confirm-timeout")
            print("confirmClick", result["confirmClick"], flush=True)
        await page.wait_for_timeout(2000)
        await shot(page, "05-final")
        result["dialogFinal"] = await page.evaluate(DIALOG_DUMP_JS)
        result["readBack"] = await page.evaluate(flow.READ_BASE_INFO_JS) if hasattr(flow, "READ_BASE_INFO_JS") else None
        print("final", json.dumps(result["dialogFinal"], ensure_ascii=False), flush=True)

        # close dialog via 取消 to leave no residue
        cancel = page.locator(".el-dialog:visible button:has-text('取消'):visible").first
        if await cancel.count():
            try:
                await cancel.click(timeout=3000)
                result["closedWithCancel"] = True
            except Exception:
                pass
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", OUT_JSON, flush=True)
        await browser.close()
        return 0 if result.get("confirmClick") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
