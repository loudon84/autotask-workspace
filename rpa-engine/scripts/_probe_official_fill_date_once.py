"""Official SRM read-only probe: open PO detail and dump delivery-date UI.

Does not fill dates or click save/sign. Write URLs are aborted.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

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

OUT_DIR = ENGINE_ROOT / "runtime-cache" / "official-fill-date-probe"
OUT_JSON = OUT_DIR / "result.json"
PO_NO = os.environ.get("PROBE_PO_NO", "POJS2610120010").strip()

DUMP_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ').trim();
  const isVisible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return false;
    const style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' && Number(style.opacity) !== 0;
  };
  const dataRpa = [...document.querySelectorAll('[data-rpa]')].slice(0, 40).map((el) => ({
    attr: el.getAttribute('data-rpa'),
    tag: el.tagName,
    text: clean(el.innerText).slice(0, 40),
    visible: isVisible(el),
  }));
  const buttons = [...document.querySelectorAll('button, .el-button, a.el-link')]
    .filter(isVisible)
    .map((el) => clean(el.innerText || el.textContent))
    .filter(Boolean)
    .slice(0, 40);
  const dateInputs = [...document.querySelectorAll('input')]
    .filter(isVisible)
    .filter((el) => {
      const ph = clean(el.getAttribute('placeholder'));
      const nearby = clean(el.closest('td, .el-form-item, .el-date-editor')?.innerText || '');
      return /日期|交货|交期/.test(ph + nearby) || el.className.includes('el-date-editor')
        || (el.closest('.el-date-editor') != null);
    })
    .map((el) => ({
      value: clean(el.value),
      placeholder: clean(el.getAttribute('placeholder')),
      readonly: !!el.readOnly,
      disabled: !!el.disabled,
      className: String(el.className || '').slice(0, 80),
      inFixedRight: !!el.closest('.el-table__fixed-right'),
      inBody: !!el.closest('.el-table__body-wrapper'),
    }))
    .slice(0, 20);
  const tags = [...document.querySelectorAll('.el-tag')]
    .filter(isVisible)
    .map((el) => clean(el.innerText))
    .filter(Boolean)
    .slice(0, 20);
  const headers = [...document.querySelectorAll('.el-table__header-wrapper th')]
    .map((th) => clean(th.innerText))
    .filter(Boolean)
    .slice(0, 30);
  const rows = [...document.querySelectorAll('.el-table__body-wrapper tbody tr')].slice(0, 5).map((tr, i) => ({
    rowIndex: i,
    cells: [...tr.querySelectorAll(':scope > td')].map((td) => clean(td.innerText)).slice(0, 12),
  }));
  return {
    hash: location.hash,
    title: clean(document.title),
    dataRpaCount: document.querySelectorAll('[data-rpa]').length,
    dataRpaSample: dataRpa,
    buttons,
    dateInputs,
    tags,
    headers,
    rows,
    pageTextHas: {
      expectedDelivery: document.body.innerText.includes('预计交货'),
      requestDelivery: document.body.innerText.includes('要求交货'),
      save: /保存/.test(document.body.innerText),
      sign: /签章/.test(document.body.innerText),
      pendingSign: document.body.innerText.includes('待签章'),
      signed: document.body.innerText.includes('已回签'),
    },
  };
}"""


async def logged_in(page) -> bool:
    selectors = (
        ".el-menu-item:has-text('订单'):visible",
        "span:has-text('订单'):visible",
        ".el-menu:has-text('订单'):visible",
        "text=个人中心",
    )
    for sel in selectors:
        try:
            await page.locator(sel).first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            continue
    return False


async def do_login(page, portal_url, username, password) -> bool:
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


async def _load_prod_portal_password() -> str:
    """Fallback: read portal credential_ref from prod Task DB (plaintext ref)."""
    try:
        import asyncpg
    except Exception:
        return ""
    env_path = ENGINE_ROOT.parent / "service" / ".env.product"
    raw = ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            raw = line.split("=", 1)[1].strip()
            break
    if not raw:
        return ""
    url = raw.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(url)
        try:
            value = await conn.fetchval(
                "SELECT credential_ref FROM public.portal_accounts WHERE id=$1",
                "9c13041f-da3d-497b-83c8-bd952abfbea4",
            )
            return str(value or "")
        finally:
            await conn.close()
    except Exception:
        return ""


async def main() -> int:
    probe.load_env_file(probe.ENV_FILE)
    portal_url = (
        os.environ.get("OFFICIAL_OCR_URL") or os.environ.get("SUPPLIER_PORTAL_URL") or ""
    ).strip() or "https://supplier.tiandy.com"
    username = (
        os.environ.get("OFFICIAL_OCR_USER") or os.environ.get("SUPPLIER_PORTAL_USERNAME") or ""
    ).strip() or "02556"
    password = os.environ.get("OFFICIAL_OCR_PASS") or os.environ.get("SUPPLIER_PORTAL_PASSWORD") or ""
    if not password:
        password = await _load_prod_portal_password()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "probedAt": datetime.now(UTC).isoformat(),
        "portalUrl": portal_url,
        "poNo": PO_NO,
    }
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
            ok = await do_login(page, portal_url, username, password)
            if not ok:
                result["ok"] = False
                result["error"] = "login_failed"
                await page.screenshot(path=str(OUT_DIR / "00-login-failed.png"), full_page=True)
                OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("login=failed")
                await browser.close()
                return 3
            await context.storage_state(path=str(state_path))
            result["login"] = {"ok": True, "via": "captcha"}
        else:
            result["login"] = {"ok": True, "reusedSession": True}

        await install_write_guard(page, dry_run=True, allow_upload=False)
        portal_root = portal_url.split("#", 1)[0].rstrip("/")

        # Try common official order list routes
        list_hashes = [
            "#/order/list",
            "#/order/pending",
            "#/supplier/orders",
            "#/order/orderList",
        ]
        opened = False
        for h in list_hashes:
            await page.goto(f"{portal_root}/{h}", wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            dump = await page.evaluate(DUMP_JS)
            result.setdefault("listProbes", []).append({"hash": h, "buttons": dump.get("buttons"), "headers": dump.get("headers")})
            # try fill order no + search
            po_input = page.locator(
                "input[placeholder*='订单']:visible, input[placeholder*='订单编号']:visible, "
                ".el-form-item:has-text('订单编号') input:visible, .el-form-item:has-text('订单号') input:visible"
            ).first
            if await po_input.count():
                try:
                    await po_input.fill(PO_NO)
                    search = page.locator("button:has-text('查询'):visible").first
                    if await search.count():
                        await search.click(timeout=4000)
                        await page.wait_for_timeout(2000)
                        opened = True
                        break
                except Exception as exc:
                    result.setdefault("listErrors", []).append({"hash": h, "error": type(exc).__name__})

        await page.screenshot(path=str(OUT_DIR / "01-list.png"), full_page=True)
        result["listDump"] = await page.evaluate(DUMP_JS)

        # click 详情 in fixed-right action column (same as prepare_erp_order)
        detail_clicked = False
        detail_error = None
        try:
            row = page.locator(".el-table__body-wrapper tbody tr").filter(has_text=PO_NO).first
            await row.wait_for(state="visible", timeout=8000)
            fixed = page.locator(".el-table__fixed-right tbody tr").filter(has_text="详情")
            # Prefer fixed-right link aligned to matched row index 0 when only one row
            candidates = [
                page.locator(".el-table__fixed-right tbody tr").nth(0).get_by_text("详情", exact=True),
                row.get_by_text("详情", exact=True),
                page.get_by_text("详情", exact=True).locator("visible=true"),
            ]
            for idx, loc in enumerate(candidates):
                try:
                    await loc.first.click(timeout=4000)
                    await page.wait_for_timeout(2500)
                    detail_clicked = True
                    result["detailClick"] = f"candidate[{idx}]"
                    break
                except Exception as exc:
                    detail_error = type(exc).__name__
                    continue
        except Exception as exc:
            detail_error = type(exc).__name__
        result["detailClicked"] = detail_clicked
        result["detailError"] = detail_error
        await page.screenshot(path=str(OUT_DIR / "02-detail.png"), full_page=True)
        result["detailDump"] = await page.evaluate(DUMP_JS)
        # wait a bit more if hash still list
        if result["detailDump"].get("hash") == "#/order/list" and detail_clicked:
            await page.wait_for_timeout(3000)
            result["detailDump"] = await page.evaluate(DUMP_JS)
            await page.screenshot(path=str(OUT_DIR / "02b-detail.png"), full_page=True)
        result["ok"] = bool(
            result["detailDump"].get("pageTextHas", {}).get("expectedDelivery")
            or (detail_clicked and result["detailDump"].get("hash") != "#/order/list")
        )
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("login", result.get("login"))
        print("detailClicked", detail_clicked, "hash", result["detailDump"].get("hash"))
        print("tags", result["detailDump"].get("tags"))
        print("buttons", result["detailDump"].get("buttons"))
        print("headers", result["detailDump"].get("headers"))
        print("dateInputs", json.dumps(result["detailDump"].get("dateInputs"), ensure_ascii=False)[:800])
        print("pageTextHas", result["detailDump"].get("pageTextHas"))
        print("dataRpaCount", result["detailDump"].get("dataRpaCount"))
        print(f"wrote {OUT_JSON}")
        await browser.close()
        return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
