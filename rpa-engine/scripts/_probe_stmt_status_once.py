"""Official SRM read-only: check the statement list status of a given date+amount.

Reuses Engine session cache; all write URLs are aborted. Does not click any
write button. Dumps the matched row's full cell texts to JSON + screenshots.
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

from nodeskclaw_rpa_engine.runtime.dry_run import install_write_guard
from nodeskclaw_rpa_engine.runtime.official_srm_login import login_official_srm
from nodeskclaw_rpa_engine.runtime.session_cache import session_cache_key
from playwright.async_api import async_playwright

import probe_tiandy_prod_readonly as probe

OUT_JSON = ENGINE_ROOT / "runtime-cache" / "stmt-status-probe" / "result.json"
SCREEN_DIR = ENGINE_ROOT / "runtime-cache" / "stmt-status-probe"
STATEMENT_HASH = "#/reconciliation/reconciliationStatement"

ROW_DUMP_JS = r"""(args) => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').replace(/ /g, ' ').trim();
  const normAmt = (v) => clean(v).replace(/,/g, '');
  const tables = [...document.querySelectorAll('.el-table')];
  const out = { rows: [], matched: null, hash: location.hash, rowCount: 0 };
  for (const table of tables) {
    const body = table.querySelector('.el-table__body-wrapper tbody')
      || table.querySelector('.el-table__fixed-body-wrapper tbody');
    if (!body) continue;
    const rows = [...body.querySelectorAll('tr')];
    out.rowCount += rows.length;
    for (let i = 0; i < rows.length; i += 1) {
      const cells = [...rows[i].querySelectorAll('td')].map((td) => clean(td.innerText));
      const joined = cells.join('|');
      out.rows.push({ rowIndex: i, cells });
      if (joined.includes(args.checkDate) && normAmt(joined).includes(normAmt(args.checkAmount))) {
        out.matched = { rowIndex: i, cells };
      }
    }
    if (out.matched) break;
  }
  return out;
}"""


async def logged_in(page) -> bool:
    try:
        loc = page.locator(
            ".el-menu-item:has-text('订单'):visible, span:has-text('订单'):visible"
        ).first
        await loc.wait_for(state="visible", timeout=8000)
        return True
    except Exception:
        return False


async def main() -> int:
    check_date = os.environ.get("PROBE_CHECK_DATE", "2026-10-09").strip()
    check_amount = os.environ.get("PROBE_CHECK_AMOUNT", "3354661.32").strip()
    status_filter = os.environ.get("PROBE_STATUS_FILTER", "").strip()
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

    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "probedAt": datetime.now(UTC).isoformat(),
        "portalUrl": portal_url,
        "checkDate": check_date,
        "checkAmount": check_amount,
        "statusFilter": status_filter or None,
    }

    cache_key = session_cache_key(portal_url, username)
    state_path = ENGINE_ROOT / "runtime-cache" / "sessions" / cache_key / "storage_state.json"
    result["sessionCache"] = str(state_path.relative_to(ENGINE_ROOT)) if state_path.is_file() else None

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
            if probe.should_block_probe_write(request.method, request.url):
                await route.abort("blockedbyclient")
                return
            await route.continue_()

        await page.route("**/*", on_route)
        await page.goto(portal_url, wait_until="domcontentloaded")
        if not await logged_in(page):
            if not password:
                result["ok"] = False
                result["error"] = "session_expired_no_password"
                OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("login=failed session_expired_no_password")
                await browser.close()
                return 3
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

            login_ctx = SimpleNamespace(
                page=page,
                credentials={"username": username, "password": password},
                selectors=login_selectors,
                events=Events(),
                portal_url=portal_url,
                artifacts=None,
                log=QuietLog(),
            )
            try:
                await login_official_srm(login_ctx, selector=selector)
            except Exception as exc:
                result["ok"] = False
                result["error"] = f"login_failed:{getattr(exc, 'code', type(exc).__name__)}"
                await page.screenshot(path=str(SCREEN_DIR / "00-login-failed.png"), full_page=True)
                OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("login=failed", result["error"])
                await browser.close()
                return 3
            if not await logged_in(page):
                result["ok"] = False
                result["error"] = "login_not_confirmed"
                await page.screenshot(path=str(SCREEN_DIR / "00-login-failed.png"), full_page=True)
                OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("login=failed login_not_confirmed")
                await browser.close()
                return 3
            result["login"] = {"ok": True, "via": "login_official_srm"}
            try:
                state_path.parent.mkdir(parents=True, exist_ok=True)
                await context.storage_state(path=str(state_path))
                result["sessionSaved"] = True
            except Exception:
                result["sessionSaved"] = False
        else:
            result["login"] = {"ok": True, "reusedSession": True}

        await install_write_guard(page, dry_run=True, allow_upload=False)
        portal_root = portal_url.split("#", 1)[0].rstrip("/")
        await page.goto(f"{portal_root}/{STATEMENT_HASH}", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        if status_filter:
            await probe.select_form_option(page, "对账状态", status_filter)
        await page.locator("button:has-text('查询'):visible").click(timeout=4000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SCREEN_DIR / "01-list.png"), full_page=True)

        dump = await page.evaluate(ROW_DUMP_JS, {"checkDate": check_date, "checkAmount": check_amount})
        result["dump"] = dump
        result["ok"] = bool(dump.get("matched"))
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("rowCount:", dump.get("rowCount"))
        if dump.get("matched"):
            print("MATCHED cells:", json.dumps(dump["matched"]["cells"], ensure_ascii=False))
        else:
            print("not matched; first rows:")
            for row in (dump.get("rows") or [])[:5]:
                print("  ", json.dumps(row["cells"], ensure_ascii=False)[:300])
        print(f"ok={result['ok']}")
        print(f"wrote {OUT_JSON}")
        await browser.close()
        return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
