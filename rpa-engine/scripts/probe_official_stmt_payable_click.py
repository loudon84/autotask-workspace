"""Official SRM: match 未对账 by date+amount, then click 收货应付 using the Flow JS.

Does not click 提交审核 / 生成对账单 / 保存. Write URLs are aborted.
Reuses Engine session cache when present so this can run without Client.
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

from nodeskclaw_rpa_engine.runtime.actionability import inspect_clickable
from nodeskclaw_rpa_engine.runtime.dry_run import install_write_guard
from nodeskclaw_rpa_engine.runtime.official_srm_login import login_official_srm
from nodeskclaw_rpa_engine.runtime.session_cache import session_cache_key
from playwright.async_api import async_playwright

import probe_tiandy_prod_readonly as probe

FLOW_PY = FLOWS / "rpa_flow_srm_stmt_upload_invoice" / "1.1.2" / "flow.py"
OUT_JSON = ENGINE_ROOT / "runtime-cache" / "tiandy-stmt-payable-click.json"
SCREEN_DIR = ENGINE_ROOT / "runtime-cache" / "tiandy-stmt-payable-click"
STATEMENT_HASH = "#/reconciliation/reconciliationStatement"
DEFAULT_DATE = "2026-04-01"
DEFAULT_AMOUNT = "5768205.32"

INSPECT_JS = r"""() => {
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
  const countPayable = (root) => [...(root || document).querySelectorAll('button, a, span, .el-button, .el-link')]
    .filter((el) => String(el.innerText || '').includes('收货应付'))
    .map((el) => ({
      visible: isVisible(el),
      disabled: !!(el.disabled || el.className.includes('is-disabled')),
      text: String(el.innerText || '').trim(),
    }));
  const table = [...document.querySelectorAll('.el-table')].sort((a, b) => (
    b.querySelectorAll('.el-table__body-wrapper tbody tr').length
    - a.querySelectorAll('.el-table__body-wrapper tbody tr').length
  ))[0];
  if (!table) return { error: 'no-table' };
  const fixedRight = table.querySelector('.el-table__fixed-right');
  return {
    hash: location.hash,
    bodyWrapperRows: table.querySelectorAll('.el-table__body-wrapper tbody tr').length,
    fixedBodyWrapperRows: table.querySelectorAll('.el-table__fixed-body-wrapper tbody tr').length,
    hasFixedRight: !!fixedRight,
    fixedRightBodyWrapperRows: fixedRight
      ? fixedRight.querySelectorAll('.el-table__body-wrapper tbody tr').length
      : 0,
    fixedRightFixedBodyRows: fixedRight
      ? fixedRight.querySelectorAll('.el-table__fixed-body-wrapper tbody tr').length
      : 0,
    payableInTable: countPayable(table),
    payableInFixedRight: countPayable(fixedRight),
  };
}"""


def load_flow():
    spec = importlib.util.spec_from_file_location("official_stmt_upload_1_1_1", FLOW_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def official_login(page, portal_url: str, username: str, password: str) -> dict:
    from types import SimpleNamespace

    selectors = {
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
        value = selectors[name]
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    ctx = SimpleNamespace(
        page=page,
        credentials={"username": username, "password": password},
        selectors=selectors,
        events=Events(),
        portal_url=portal_url,
        artifacts=None,
        log=QuietLog(),
    )
    await login_official_srm(ctx, selector=selector)
    return {"ok": True, "via": "login_official_srm"}


async def screenshot(page, name: str) -> None:
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(SCREEN_DIR / f"{name}.png"), full_page=True)


async def logged_in(page) -> bool:
    try:
        loc = page.locator(".el-menu-item:has-text('订单'):visible, span:has-text('订单'):visible")
        return await loc.count() > 0
    except Exception:
        return False


async def main() -> int:
    check_date = os.environ.get("PROBE_CHECK_DATE", DEFAULT_DATE).strip()
    check_amount = os.environ.get("PROBE_CHECK_AMOUNT", DEFAULT_AMOUNT).strip()
    probe.load_env_file(probe.ENV_FILE)
    portal_url = (
        os.environ.get("OFFICIAL_OCR_URL")
        or os.environ.get("SUPPLIER_PORTAL_URL")
        or ""
    ).strip() or "https://supplier.tiandy.com"
    username = (
        os.environ.get("OFFICIAL_OCR_USER")
        or os.environ.get("SUPPLIER_PORTAL_USERNAME")
        or ""
    ).strip() or "02556"
    password = os.environ.get("OFFICIAL_OCR_PASS") or os.environ.get("SUPPLIER_PORTAL_PASSWORD") or ""
    flow = load_flow()
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "probedAt": datetime.now(UTC).isoformat(),
        "portalUrl": portal_url,
        "username": username,
        "checkDate": check_date,
        "checkAmount": check_amount,
        "flow": "rpa_flow_srm_stmt_upload_invoice/1.1.2",
    }

    cache_key = session_cache_key(portal_url, username)
    state_path = ENGINE_ROOT / "runtime-cache" / "sessions" / cache_key / "storage_state.json"
    result["sessionCache"] = str(state_path.relative_to(ENGINE_ROOT)) if state_path.is_file() else None

    async with async_playwright() as playwright:
        browser, _unused_context, _unused_page, browser_label = await probe.launch_browser(
            playwright, headless=True
        )
        await _unused_page.close()
        await _unused_context.close()
        context_kwargs = {"viewport": {"width": 1600, "height": 1000}}
        if state_path.is_file():
            context_kwargs["storage_state"] = str(state_path)
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        result["browser"] = browser_label

        async def on_route(route):
            request = route.request
            if probe.should_block_probe_write(request.method, request.url):
                await route.abort("blockedbyclient")
                return
            await route.continue_()

        await page.route("**/*", on_route)
        await page.goto(portal_url, wait_until="domcontentloaded")
        if not await logged_in(page):
            if not password:
                result["login"] = {"ok": False, "reason": "session_expired_no_password"}
                OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("login=failed session_expired_no_password")
                await browser.close()
                return 3
            try:
                login_info = await official_login(page, portal_url, username, password)
            except Exception as exc:
                result["login"] = {
                    "ok": False,
                    "via": "login_official_srm",
                    "error": type(exc).__name__,
                    "code": getattr(exc, "code", ""),
                }
                await screenshot(page, "login-failed")
                OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("login=failed")
                await browser.close()
                return 3
            result["login"] = login_info
            if not await logged_in(page):
                result["login"]["ok"] = False
                await screenshot(page, "login-not-in")
                OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("login=failed")
                await browser.close()
                return 3
        else:
            result["login"] = {"ok": True, "reusedSession": True}

        await install_write_guard(page, dry_run=True, allow_upload=False)
        portal_root = portal_url.split("#", 1)[0].rstrip("/")
        await page.goto(f"{portal_root}/{STATEMENT_HASH}", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        await probe.select_form_option(page, "对账状态", "未对账")
        await page.locator("button:has-text('查询'):visible").click(timeout=4000)
        await page.wait_for_timeout(1500)
        await screenshot(page, "01-unchecked-list")

        result["inspect"] = await page.evaluate(INSPECT_JS)
        found = await page.evaluate(
            flow.FIND_STATEMENT_JS,
            {"checkDate": check_date, "checkAmount": check_amount},
        )
        result["find"] = found
        print(
            "find",
            json.dumps(found, ensure_ascii=False),
            flush=True,
        )
        if not isinstance(found, dict) or not found.get("matched"):
            result["click"] = None
            result["ok"] = False
            OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("match=failed")
            await browser.close()
            return 2

        click = await page.evaluate(
            flow.CLICK_PAYABLE_JS,
            {"rowIndex": int(found["rowIndex"]), "buttonText": "收货应付"},
        )
        result["click"] = click
        print(f"click={click}", flush=True)
        if click != "ok":
            try:
                await page.locator(".el-table__fixed-right tbody tr").nth(
                    int(found["rowIndex"])
                ).get_by_text("收货应付").locator("visible=true").first.click(timeout=4000)
                result["click"] = "ok-playwright-fallback"
                click = "ok"
            except Exception as exc:
                result["fallbackError"] = type(exc).__name__

        await page.wait_for_timeout(1500)
        await screenshot(page, "02-after-payable-click")
        payable_visible = await page.locator(
            "button:has-text('提交审核'):visible, button:has-text('扫描发票'):visible"
        ).count()
        result["payablePageVisible"] = payable_visible > 0
        result["scanClickable"] = await probe_button(
            page,
            "button:has-text('扫描发票信息'):visible, button:has-text('扫描发票'):visible",
            "扫描发票",
        )
        result["submitClickable"] = await probe_button(
            page,
            "button:has-text('提交审核'):visible",
            "提交审核",
        )
        try:
            result["readBaseInfo"] = await page.evaluate(flow.READ_BASE_INFO_JS)
            result["readBaseInfoOk"] = True
        except Exception as exc:
            result["readBaseInfo"] = {"error": type(exc).__name__, "message": str(exc).split("\n", 1)[0][:200]}
            result["readBaseInfoOk"] = False
        result["scanDialog"] = await probe_scan_dialog(page)
        scan_ok = bool(result["scanClickable"].get("trialOk"))
        submit = result["submitClickable"]
        if not submit.get("present"):
            submit_ok = False
        elif submit.get("disabled"):
            submit_ok = True
        else:
            submit_ok = bool(submit.get("trialOk"))
        result["ok"] = (
            click in {"ok", "ok-playwright-fallback"}
            and payable_visible > 0
            and scan_ok
            and submit_ok
            and result.get("readBaseInfoOk")
        )
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"payablePageVisible={result['payablePageVisible']}")
        print("scan", json.dumps(result["scanClickable"], ensure_ascii=False))
        print("submit", json.dumps(result["submitClickable"], ensure_ascii=False))
        print("readBaseInfo", json.dumps(result.get("readBaseInfo"), ensure_ascii=False))
        print("scanDialog", json.dumps(result.get("scanDialog"), ensure_ascii=False))
        print(f"ok={result['ok']}")
        print(f"wrote {OUT_JSON}")
        await browser.close()
        return 0 if result["ok"] else 4


async def probe_scan_dialog(page) -> dict:
    scan = page.locator(
        "button:has-text('扫描发票信息'):visible, button:has-text('扫描发票'):visible"
    ).first
    try:
        await scan.click(timeout=4000)
    except Exception as exc:
        return {"opened": False, "error": type(exc).__name__}
    await page.wait_for_timeout(1200)
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(SCREEN_DIR / "03-scan-dialog.png"), full_page=True)
    info = await page.evaluate(
        r"""() => {
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
                className: String(btn.className || '').slice(0, 80),
              })).filter((item) => item.text),
              fileInputs: dialog.querySelectorAll('input[type="file"]').length,
            }));
          return {
            dialogs,
            pageButtons: [...document.querySelectorAll('button, .el-button')]
              .filter(isVisible)
              .map((btn) => clean(btn.innerText))
              .filter(Boolean)
              .slice(0, 30),
          };
        }"""
    )
    cancel = page.locator(
        ".el-dialog:visible button:has-text('取消'):visible, "
        ".el-message-box:visible button:has-text('取消'):visible"
    ).first
    closed = False
    if await cancel.count():
        try:
            await cancel.click(timeout=3000)
            closed = True
        except Exception:
            await page.keyboard.press("Escape")
            closed = True
    else:
        await page.keyboard.press("Escape")
    info["closedWithCancel"] = closed
    return info


async def probe_button(page, selector: str, name: str) -> dict:
    loc = page.locator(selector).locator("visible=true").first
    count = await loc.count()
    if count == 0:
        return {"name": name, "present": False, "trialOk": False}
    report = await inspect_clickable(loc)
    report["name"] = name
    report["present"] = True
    return report


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
