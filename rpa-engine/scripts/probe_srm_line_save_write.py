"""受控写探测：验证待签章详情「按行保存」是否真正持久化。

只写一行预计交货日期并立即读回；记录网络方法类型（不含请求体/凭据）。
凭据只从环境变量读取：SUPPLIER_PORTAL_URL / SUPPLIER_PORTAL_USERNAME / SUPPLIER_PORTAL_PASSWORD。
可选：PROBE_PO_NO（默认 POJS2607180002）、PROBE_LINE_NO（默认 10）、PROBE_DATE（默认 2026-10-01）。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys

from playwright.async_api import async_playwright

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


def resolve_captcha_code(image_src: str | None) -> str | None:
    if not image_src:
        return None
    clean = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


READ_LINE_JS = r"""({ lineNo }) => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const root = document.querySelector("[data-rpa='pend-order-detail-page'], [data-rpa='order-detail-page']");
  if (!root) return { error: 'detail_missing' };
  const hosts = [...root.querySelectorAll(`[data-rpa='pend-order-detail-expected-date-${lineNo}']`)].map((el) => {
    const input = el.querySelector('input');
    const fixedRight = !!el.closest('.el-table__fixed-right');
    const fixedLeft = !!el.closest('.el-table__fixed') && !fixedRight;
    const body = !!el.closest('.el-table__body-wrapper') && !el.closest('.el-table__fixed');
    return {
      section: fixedRight ? 'fixed-right' : fixedLeft ? 'fixed-left' : body ? 'body' : 'other',
      inputValue: input ? clean(input.value) : null,
      inputReadonly: input ? !!input.readOnly : null,
      visible: !!(el.offsetParent || (input && input.offsetParent)),
    };
  });
  const saves = [...root.querySelectorAll(`[data-rpa='pend-order-detail-save-line-${lineNo}']`)].map((el) => ({
    section: el.closest('.el-table__fixed-right')
      ? 'fixed-right'
      : el.closest('.el-table__fixed')
        ? 'fixed-left'
        : el.closest('.el-table__body-wrapper')
          ? 'body'
          : 'other',
    disabled: !!el.disabled,
    visible: !!el.offsetParent,
  }));
  return { url: location.href, hosts, saves };
}"""


async def fill_and_save(page, line_no: str, date_value: str) -> dict:
    # Prefer fixed-right (action/date columns), then body; never interact with all clones.
    candidates = [
        f".el-table__fixed-right [data-rpa='pend-order-detail-expected-date-{line_no}'] input.el-input__inner",
        f".el-table__body-wrapper [data-rpa='pend-order-detail-expected-date-{line_no}'] input.el-input__inner",
        f"[data-rpa='pend-order-detail-expected-date-{line_no}'] input.el-input__inner",
    ]
    save_candidates = [
        f".el-table__fixed-right [data-rpa='pend-order-detail-save-line-{line_no}']",
        f".el-table__body-wrapper [data-rpa='pend-order-detail-save-line-{line_no}']",
        f"[data-rpa='pend-order-detail-save-line-{line_no}']",
    ]
    used_date = None
    for sel in candidates:
        loc = page.locator(sel).first
        if await loc.count() == 0:
            continue
        try:
            await loc.wait_for(state="visible", timeout=3000)
            await loc.click()
            await loc.fill(date_value)
            await loc.press("Enter")
            used_date = sel
            break
        except Exception:
            continue
    if used_date is None:
        raise RuntimeError("date_input_not_found")
    await page.wait_for_timeout(300)
    used_save = None
    for sel in save_candidates:
        loc = page.locator(sel).first
        if await loc.count() == 0:
            continue
        try:
            await loc.wait_for(state="visible", timeout=3000)
            await loc.click(timeout=10000)
            used_save = sel
            break
        except Exception:
            continue
    if used_save is None:
        raise RuntimeError("save_button_not_found")
    return {"dateSelector": used_date, "saveSelector": used_save}


async def main() -> int:
    portal_url = os.environ.get("SUPPLIER_PORTAL_URL", "").strip().rstrip("/")
    username = os.environ.get("SUPPLIER_PORTAL_USERNAME", "").strip()
    password = os.environ.get("SUPPLIER_PORTAL_PASSWORD", "")
    po_no = os.environ.get("PROBE_PO_NO", "POJS2607180002").strip().upper()
    line_no = os.environ.get("PROBE_LINE_NO", "10").strip()
    date_value = os.environ.get("PROBE_DATE", "2026-10-01").strip()
    if not portal_url or not username or not password:
        print("缺少 SUPPLIER_PORTAL_URL / SUPPLIER_PORTAL_USERNAME / SUPPLIER_PORTAL_PASSWORD")
        return 2

    network: list[dict] = []
    browsers_path = os.environ.get(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"),
    )
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chromium-headless-shell", headless=True)
        page = await browser.new_page()

        def on_request(req):
            if req.resource_type in {"xhr", "fetch"}:
                network.append(
                    {
                        "phase": "request",
                        "method": req.method,
                        "resourceType": req.resource_type,
                        "urlPath": re.sub(r"https?://[^/]+", "", req.url)[:180],
                    }
                )

        def on_response(resp):
            req = resp.request
            if req.resource_type in {"xhr", "fetch"}:
                network.append(
                    {
                        "phase": "response",
                        "method": req.method,
                        "status": resp.status,
                        "urlPath": re.sub(r"https?://[^/]+", "", req.url)[:180],
                    }
                )

        page.on("request", on_request)
        page.on("response", on_response)

        await page.goto(portal_url, wait_until="domcontentloaded")
        captcha = page.locator("img[data-rpa='login-captcha-image']")
        await captcha.wait_for(state="visible", timeout=10000)
        code = resolve_captcha_code(await captcha.get_attribute("src"))
        if not code:
            print(json.dumps({"error": "captcha_unknown"}, ensure_ascii=False))
            await browser.close()
            return 3
        await page.fill("[data-rpa='login-username']", username)
        await page.fill("[data-rpa='login-password']", password)
        await page.fill("[data-rpa='login-captcha']", code)
        agreement = page.locator("[data-rpa='login-agreement'] input[type='checkbox']")
        if not await agreement.is_checked():
            await agreement.check()
        await page.click("button[data-rpa='login-submit']")
        await page.locator("[data-rpa='portal-env-tag']").wait_for(state="visible", timeout=15000)

        await page.goto(f"{portal_url}/#/supplier/orders", wait_until="domcontentloaded")
        await page.locator("[data-rpa='order-list-page']").wait_for(state="visible", timeout=15000)
        await page.fill("[data-rpa='order-no-input']", po_no)
        await page.click("[data-rpa='order-search-btn']")
        await page.locator(f"[data-rpa='order-row-{po_no}']:visible").wait_for(state="visible", timeout=15000)
        await page.click(f"[data-rpa='order-detail-{po_no}']:visible")
        await page.locator("[data-rpa='pend-order-detail-page'], [data-rpa='order-detail-page']").wait_for(
            state="visible", timeout=15000
        )
        await page.locator(
            f"[data-rpa='pend-order-detail-no-{po_no}']:visible, [data-rpa='order-detail-no-{po_no}']:visible"
        ).wait_for(state="visible", timeout=15000)
        before = await page.evaluate(READ_LINE_JS, {"lineNo": line_no})
        used = await fill_and_save(page, line_no, date_value)
        after_fill = await page.evaluate(READ_LINE_JS, {"lineNo": line_no})
        # wait for toast if any
        try:
            await page.locator(".el-message--success").wait_for(state="visible", timeout=5000)
            toast = "success"
        except Exception:
            try:
                await page.locator(".el-message--error").wait_for(state="visible", timeout=1000)
                toast = "error"
            except Exception:
                toast = "none"
        await page.wait_for_timeout(800)
        after_save = await page.evaluate(READ_LINE_JS, {"lineNo": line_no})
        await page.reload(wait_until="domcontentloaded")
        try:
            await page.locator("[data-rpa='pend-order-detail-page'], [data-rpa='order-detail-page']").wait_for(
                state="visible", timeout=8000
            )
        except Exception:
            # reload may drop hash route; re-open via list like Flow would need to
            await page.goto(f"{portal_url}/#/supplier/orders", wait_until="domcontentloaded")
            await page.locator("[data-rpa='order-list-page']").wait_for(state="visible", timeout=15000)
            await page.fill("[data-rpa='order-no-input']", po_no)
            await page.click("[data-rpa='order-search-btn']")
            await page.locator(f"[data-rpa='order-row-{po_no}']:visible").wait_for(state="visible", timeout=15000)
            await page.click(f"[data-rpa='order-detail-{po_no}']:visible")
            await page.locator("[data-rpa='pend-order-detail-page'], [data-rpa='order-detail-page']").wait_for(
                state="visible", timeout=15000
            )
        await page.wait_for_timeout(800)
        after_reload = await page.evaluate(READ_LINE_JS, {"lineNo": line_no})
        await browser.close()

    writes = [
        item
        for item in network
        if item.get("method") in {"POST", "PUT", "PATCH", "DELETE"} and item.get("phase") == "request"
    ]
    def any_value(snapshot):
        if not isinstance(snapshot, dict):
            return None
        for host in snapshot.get("hosts") or []:
            if host.get("inputValue"):
                return host.get("inputValue")
        return None

    result = {
        "poNo": po_no,
        "lineNo": line_no,
        "dateValue": date_value,
        "usedSelectors": used,
        "before": before,
        "afterFill": after_fill,
        "toast": toast,
        "afterSave": after_save,
        "afterReload": after_reload,
        "writeRequestCount": len(writes),
        "writeRequests": writes[:20],
        "xhrFetchCount": len([x for x in network if x.get("phase") == "request"]),
        "persisted": any_value(after_reload) == date_value,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["persisted"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
