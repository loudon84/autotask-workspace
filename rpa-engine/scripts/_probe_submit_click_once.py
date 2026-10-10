"""Official SRM: replay the submit_review flow up to the 提交审核 click, then
observe what actually happens (toast types/texts, fired API requests).

Safety: the final /statement/submit request is ABORTED (never reaches SRM).
The invoice scan/upload runs for real (same as every flow run; it does not
persist statement state by itself).
"""

from __future__ import annotations

import asyncio
import importlib.util
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
FLOWS = ENGINE_ROOT.parent / "rpa-flows"
sys.path.insert(0, str(ENGINE_ROOT / "src"))
sys.path.insert(0, str(SCRIPTS))

from nodeskclaw_rpa_engine.runtime.official_srm_login import login_official_srm
from nodeskclaw_rpa_engine.runtime.session_cache import session_cache_key
from playwright.async_api import async_playwright

import probe_tiandy_prod_readonly as probe

FLOW_PY = FLOWS / "rpa_flow_srm_stmt_submit_review" / "1.1.6" / "flow.py"
OUT_JSON = ENGINE_ROOT / "runtime-cache" / "submit-click-probe" / "result.json"
SCREEN_DIR = ENGINE_ROOT / "runtime-cache" / "submit-click-probe"
STATEMENT_HASH = "#/reconciliation/reconciliationStatement"
INVOICE_PDF = ENGINE_ROOT / "runtime-cache" / "invoice-sample.pdf"

TOAST_DUMP_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  return [...document.querySelectorAll('.el-message')].map((el) => ({
    className: String(el.className || ''),
    text: clean(el.innerText),
  })).filter((t) => t.text);
}"""


def load_flow():
    spec = importlib.util.spec_from_file_location("official_stmt_submit_1_1_6", FLOW_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def logged_in(page) -> bool:
    try:
        loc = page.locator(
            ".el-menu-item:has-text('订单'):visible, span:has-text('订单'):visible"
        ).first
        await loc.wait_for(state="visible", timeout=8000)
        return True
    except Exception:
        return False


async def do_login(page, portal_url, username, password):
    from types import SimpleNamespace

    login_selectors = {
        "username": "input[placeholder='账号或手机号码']:visible",
        "password": "input[type='password']:visible",
        "captcha": "input[placeholder='验证码']:visible",
        "captcha_image": ".el-form-item:has(input[placeholder='验证码']) img:visible",
        "agreement": ".userAgree .el-checkbox:visible .el-checkbox__inner, .userAgree .el-checkbox:visible",
        "login_button": "button:has-text('登录'):visible",
        "login_error": ".el-message--error",
        "login_success": ".el-menu-item:has-text('订单'):visible, span:has-text('订单'):visible",
    }

    class Events:
        async def emit(self, type, message="", payload=None, **kwargs):  # noqa: A002
            return None

    class QuietLog:
        async def info(self, message, extra=None):
            return None

    def selector(name, **values):
        value = login_selectors[name]
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    ctx = SimpleNamespace(
        page=page,
        credentials={"username": username, "password": password},
        selectors=login_selectors,
        events=Events(),
        portal_url=portal_url,
        artifacts=None,
        log=QuietLog(),
    )
    await login_official_srm(ctx, selector=selector)
    return await logged_in(page)


async def main() -> int:
    check_date = os.environ.get("PROBE_CHECK_DATE", "2026-10-09").strip()
    check_amount = os.environ.get("PROBE_CHECK_AMOUNT", "3354661.32").strip()
    probe.load_env_file(probe.ENV_FILE)
    portal_url = (
        os.environ.get("OFFICIAL_OCR_URL") or os.environ.get("SUPPLIER_PORTAL_URL") or ""
    ).strip() or "https://supplier.tiandy.com"
    username = (
        os.environ.get("OFFICIAL_OCR_USER") or os.environ.get("SUPPLIER_PORTAL_USERNAME") or ""
    ).strip() or "02556"
    password = os.environ.get("OFFICIAL_OCR_PASS") or os.environ.get("SUPPLIER_PORTAL_PASSWORD") or ""

    flow = load_flow()
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "probedAt": datetime.now(UTC).isoformat(),
        "checkDate": check_date,
        "checkAmount": check_amount,
        "invoicePdf": str(INVOICE_PDF),
        "invoicePdfExists": INVOICE_PDF.is_file(),
    }
    fired_requests = []

    cache_key = session_cache_key(portal_url, username)
    state_path = ENGINE_ROOT / "runtime-cache" / "sessions" / cache_key / "storage_state.json"

    async with async_playwright() as playwright:
        browser, _ctx, _page, browser_label = await probe.launch_browser(playwright, headless=True)
        await _page.close()
        await _ctx.close()
        context_kwargs = {"viewport": {"width": 1600, "height": 1000}}
        if state_path.is_file():
            context_kwargs["storage_state"] = str(state_path)
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        result["browser"] = browser_label

        async def on_route(route):
            request = route.request
            url = request.url.lower()
            method = request.method.upper()
            if "/statement/submit" in url:
                fired_requests.append({"method": method, "url": request.url, "action": "aborted"})
                await route.abort("blockedbyclient")
                return
            if probe.should_block_probe_write(method, request.url) and "/statement/invoice/upload" not in url:
                fired_requests.append({"method": method, "url": request.url, "action": "blocked-other-write"})
                await route.abort("blockedbyclient")
                return
            await route.continue_()

        await page.route("**/*", on_route)
        await page.goto(portal_url, wait_until="domcontentloaded")
        if not await logged_in(page):
            ok = await do_login(page, portal_url, username, password)
            if not ok:
                result["ok"] = False
                result["error"] = "login_failed"
                await page.screenshot(path=str(SCREEN_DIR / "00-login-failed.png"), full_page=True)
                OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("login=failed")
                await browser.close()
                return 3
            try:
                state_path.parent.mkdir(parents=True, exist_ok=True)
                await context.storage_state(path=str(state_path))
            except Exception:
                pass
            result["login"] = {"ok": True, "via": "captcha"}
        else:
            result["login"] = {"ok": True, "reusedSession": True}

        # open statement list, match row, click 收货应付
        portal_root = portal_url.split("#", 1)[0].rstrip("/")
        await page.goto(f"{portal_root}/{STATEMENT_HASH}", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        await probe.select_form_option(page, "对账状态", "未对账")
        await page.locator("button:has-text('查询'):visible").click(timeout=4000)
        await page.wait_for_timeout(2000)
        found = await page.evaluate(
            flow.FIND_STATEMENT_JS, {"checkDate": check_date, "checkAmount": check_amount}
        )
        result["find"] = found
        if not isinstance(found, dict) or not found.get("matched"):
            result["ok"] = False
            OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("match=failed")
            await browser.close()
            return 2
        click = await page.evaluate(
            flow.CLICK_PAYABLE_JS, {"rowIndex": int(found["rowIndex"]), "buttonText": "收货应付"}
        )
        result["payableClick"] = click
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(SCREEN_DIR / "01-payable.png"), full_page=True)

        # scan invoice exactly like the flow does
        scan = page.locator(
            "button:has-text('扫描发票信息'):visible, button:has-text('扫描发票'):visible"
        ).first
        await scan.click(timeout=4000)
        file_input = page.locator(".el-dialog:visible input[type='file'], input[type='file']")
        await file_input.first.wait_for(state="attached", timeout=8000)
        await file_input.first.set_input_files(str(INVOICE_PDF))
        # wait upload: mask appear/clear or success toast
        mask = page.locator(".el-loading-mask:visible")
        for _ in range(120):
            if await page.locator(".el-message--success").count():
                break
            if await mask.count():
                break
            await page.wait_for_timeout(400)
        for _ in range(150):
            if await page.locator(".el-message--success").count():
                break
            if await mask.count() == 0:
                break
            await page.wait_for_timeout(400)
        await page.wait_for_timeout(400)
        confirm = page.locator(
            ".el-dialog:visible .el-dialog__footer button:has-text('确定'):visible, "
            ".el-dialog:visible button.el-button--primary:has-text('确定'):visible, "
            ".el-message-box:visible button:has-text('确定'):visible, "
            ".el-dialog:visible button:has-text('确认'):visible"
        ).first
        await confirm.click(timeout=4000)
        await page.wait_for_timeout(1000)
        try:
            info = await page.evaluate(flow.READ_BASE_INFO_JS)
        except Exception as exc:
            info = {"error": type(exc).__name__}
        result["readBackAfterScan"] = info
        await page.screenshot(path=str(SCREEN_DIR / "02-after-scan.png"), full_page=True)

        # let any leftover toasts expire (el-message default 3s)
        await page.wait_for_timeout(4000)
        result["toastsBeforeSubmitClick"] = await page.evaluate(TOAST_DUMP_JS)

        # click 提交审核 and observe
        submit = page.locator("button:has-text('提交审核'):visible").first
        await submit.click(timeout=4000)
        toast_timeline = []
        for _ in range(20):
            await page.wait_for_timeout(400)
            toasts = await page.evaluate(TOAST_DUMP_JS)
            if toasts:
                toast_timeline.append({"toasts": toasts})
        await page.wait_for_timeout(1000)
        result["toastsAfterSubmitClick"] = toast_timeline
        result["hashAfterClick"] = await page.evaluate("() => location.hash")
        await page.screenshot(path=str(SCREEN_DIR / "03-after-submit-click.png"), full_page=True)
        result["firedRequests"] = fired_requests
        result["ok"] = True
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("readBack:", json.dumps(info, ensure_ascii=False)[:300])
        print("toastsBefore:", json.dumps(result["toastsBeforeSubmitClick"], ensure_ascii=False))
        print("toastTimeline:", json.dumps(toast_timeline, ensure_ascii=False)[:1200])
        print("firedRequests:", json.dumps(fired_requests, ensure_ascii=False))
        print("hashAfter:", result["hashAfterClick"])
        print(f"wrote {OUT_JSON}")
        await browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
