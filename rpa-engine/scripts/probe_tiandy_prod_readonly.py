"""天地伟业正式 SRM 只读探测。

只登录、点菜单、读列表/详情 DOM。不点保存、签章、生成对账单、提交审批。
写类 URL（save/sign/generate/submit 等）会被 Playwright 拦截。
凭据来自环境变量或 runtime-cache/tiandy-probe.env（该目录已 gitignore）。不打印密码。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"),
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

CACHE_DIR = ROOT / "runtime-cache"
ENV_FILE = CACHE_DIR / "tiandy-probe.env"
OUT_JSON = CACHE_DIR / "tiandy-prod-probe.json"
SCREEN_DIR = CACHE_DIR / "tiandy-prod-probe"

FORBIDDEN_CLICK = ("生成对账单", "提交审批", "提交审核", "签章")
FORBIDDEN_CLICK_EXACT = {"保存", "提交"}
WRITE_URL_MARKERS = (
    "generate",
    "savesubmit",
    "/save",
    "sign",
    "approve",
    "submit",
    "delete",
    "remove",
    "createbill",
    "createreconcil",
    "createcheck",
)
QUERY_URL_MARKERS = ("query", "search", "list", "page", "select", "find", "load")
LOGIN_URL_MARKERS = ("login", "captcha", "auth", "oauth", "verify", "sms")

PAGE_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const rpa = [...document.querySelectorAll('[data-rpa]')].map((el) => el.getAttribute('data-rpa'));
  const tables = [...document.querySelectorAll('.el-table, table')].map((table) => {
    const headers = [...table.querySelectorAll('thead th, .el-table__header-wrapper th')].map((th) => clean(th.innerText));
    const bodyRows = table.querySelectorAll('tbody tr, .el-table__body-wrapper tbody tr');
    const first = table.querySelector('tbody tr, .el-table__body-wrapper tbody tr');
    const firstButtons = first
      ? [...first.querySelectorAll('button, a, .el-button')].map((el) => clean(el.innerText)).filter(Boolean)
      : [];
    const sample = first
      ? [...first.querySelectorAll('td')].map((td) => clean(td.innerText)).slice(0, 12)
      : [];
    return { headers, rowCount: bodyRows.length, firstButtons, sample };
  }).filter((item) => item.headers.length || item.rowCount);
  const buttons = [...document.querySelectorAll('button, .el-button, a.el-link')].map((btn) => ({
    text: clean(btn.innerText || btn.getAttribute('aria-label') || ''),
    disabled: !!(btn.disabled || btn.getAttribute('disabled') || btn.className.includes('is-disabled')),
  })).filter((item) => item.text).slice(0, 60);
  const menus = [...document.querySelectorAll(
    '.el-menu-item, .el-submenu__title, .ant-menu-item, .ant-menu-submenu-title, nav a, .sidebar a'
  )].map((el) => clean(el.innerText)).filter(Boolean).slice(0, 80);
  const inputs = [...document.querySelectorAll('input')].slice(0, 20).map((el) => ({
    type: el.type || '',
    placeholder: el.placeholder || '',
    name: el.name || '',
    visible: !!(el.offsetParent || el.getClientRects().length),
  }));
  return {
    url: location.href,
    hash: location.hash,
    title: document.title,
    rpaCount: new Set(rpa).size,
    rpa: [...new Set(rpa)].slice(0, 40),
    menus,
    tables,
    buttons,
    inputs,
  };
}"""

ROWS_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const tables = [...document.querySelectorAll('.el-table')];
  const table = tables.sort((a, b) => (
    b.querySelectorAll('.el-table__body-wrapper tbody tr').length
    - a.querySelectorAll('.el-table__body-wrapper tbody tr').length
  ))[0];
  if (!table) return { headers: [], rows: [], rowCount: 0 };
  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.innerText));
  const rows = [...table.querySelectorAll('.el-table__body-wrapper tbody tr')].slice(0, 8).map((tr) => {
    const cells = [...tr.querySelectorAll(':scope > td')].map((td) => clean(td.innerText));
    const row = {};
    headers.forEach((header, index) => { if (header) row[header] = cells[index] || ''; });
    row._buttons = [...tr.querySelectorAll('button, a, .el-button, .el-link')].map((el) => clean(el.innerText)).filter(Boolean);
    return row;
  });
  return { headers, rowCount: table.querySelectorAll('.el-table__body-wrapper tbody tr').length, rows };
}"""


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_credentials() -> tuple[str, str, str]:
    load_env_file(ENV_FILE)
    portal_url = os.environ.get("SUPPLIER_PORTAL_URL", "").strip() or "https://supplier.tiandy.com"
    username = os.environ.get("SUPPLIER_PORTAL_USERNAME", "").strip()
    password = os.environ.get("SUPPLIER_PORTAL_PASSWORD", "")
    if not username or not password:
        raise SystemExit("缺少 SUPPLIER_PORTAL_USERNAME / SUPPLIER_PORTAL_PASSWORD")
    return portal_url, username, password


def is_forbidden_click(text: str) -> bool:
    value = re.sub(r"\s+", "", text or "")
    if not value:
        return False
    if value in FORBIDDEN_CLICK_EXACT:
        return True
    return any(token in value for token in FORBIDDEN_CLICK)


def should_block_probe_write(method: str, url: str) -> bool:
    verb = (method or "GET").upper()
    if verb not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    target = (url or "").lower()
    if any(marker in target for marker in LOGIN_URL_MARKERS):
        return False
    if any(marker in target for marker in QUERY_URL_MARKERS):
        return False
    return any(marker in target for marker in WRITE_URL_MARKERS)


def redact_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def try_ocr(image_bytes: bytes) -> str | None:
    try:
        import ddddocr
    except Exception:
        return None
    try:
        ocr = ddddocr.DdddOcr(show_ad=False)
        text = str(ocr.classification(image_bytes) or "").strip()
        return text or None
    except Exception:
        return None


async def wait_for_human_captcha_code(timeout_seconds: int = 180) -> str | None:
    path = SCREEN_DIR / "captcha-code.txt"
    if path.exists():
        path.unlink()
    (SCREEN_DIR / "captcha-waiting.txt").write_text("waiting", encoding="utf-8")
    print("captcha_waiting", flush=True)
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        if path.is_file():
            code = path.read_text(encoding="utf-8").strip()
            if code:
                path.unlink(missing_ok=True)
                (SCREEN_DIR / "captcha-waiting.txt").unlink(missing_ok=True)
                return code
        await asyncio.sleep(1)
    (SCREEN_DIR / "captcha-waiting.txt").unlink(missing_ok=True)
    return None


async def screenshot(page, name: str) -> None:
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(SCREEN_DIR / f"{name}.png"), full_page=True)


async def safe_click_text(page, texts: tuple[str, ...], *, timeout: int = 4000) -> str | None:
    for text in texts:
        if is_forbidden_click(text):
            continue
        locators = [
            page.get_by_role("menuitem", name=text),
            page.get_by_text(text, exact=True),
            page.locator(f"xpath=//*[normalize-space()='{text}']"),
        ]
        for locator in locators:
            try:
                target = locator.first
                if await target.count() == 0:
                    continue
                label = (await target.inner_text()).strip()
                if is_forbidden_click(label):
                    continue
                await target.click(timeout=timeout)
                await page.wait_for_timeout(1200)
                return text
            except Exception:
                continue
    return None


async def click_query_if_present(page) -> bool:
    clicked = await safe_click_text(page, ("查询", "搜索"), timeout=2500)
    if clicked:
        await page.wait_for_timeout(1500)
        return True
    return False


CAPTCHA_IMG_JS = r"""() => {
  const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
  [...document.querySelectorAll('img[data-probe-captcha]')].forEach((el) => el.removeAttribute('data-probe-captcha'));
  const input = [...document.querySelectorAll('input')].find(
    (el) => el.placeholder === '验证码' && visible(el)
  );
  if (!input) return { error: 'captcha_input_missing' };
  let picked = null;
  let node = input;
  for (let i = 0; i < 8 && node && !picked; i++) {
    const imgs = [...node.querySelectorAll('img')].filter(visible);
    picked = imgs.find((el) => {
      const w = el.naturalWidth || el.width;
      const h = el.naturalHeight || el.height;
      const src = String(el.src || '');
      const cls = String(el.className || '');
      // 真正验证码：data URL、扁长矩形；排除品牌 login_img
      return src.startsWith('data:image')
        && !cls.includes('login_img')
        && w >= 70 && w <= 200
        && h >= 28 && h <= 50;
    }) || null;
    node = node.parentElement;
  }
  if (picked) picked.setAttribute('data-probe-captcha', '1');
  return {
    picked: picked ? (picked.naturalWidth || picked.width) : 0,
    pickedClass: picked ? String(picked.className || '') : '',
    srcHead: picked ? String(picked.src || '').slice(0, 48) : '',
  };
}"""


async def resolve_captcha_image(page):
    info = await page.evaluate(CAPTCHA_IMG_JS)
    locator = page.locator("img[data-probe-captcha='1']").first
    # 优先从选中的验证码 img 的 data URL 落盘，避免截到品牌图
    try:
        data_url = await page.evaluate(
            """() => {
              const el = document.querySelector('img[data-probe-captcha=\"1\"]');
              return el && el.src ? el.src : '';
            }"""
        )
        if isinstance(data_url, str) and data_url.startswith("data:image"):
            import base64

            _header, _, b64 = data_url.partition(",")
            if b64:
                raw = base64.b64decode(b64)
                SCREEN_DIR.mkdir(parents=True, exist_ok=True)
                (SCREEN_DIR / "login-captcha.png").write_bytes(raw)
                info = dict(info or {})
                info["fromDataUrl"] = True
                info["bytes"] = len(raw)
    except Exception as exc:
        info = dict(info or {})
        info["dataUrlError"] = type(exc).__name__
    return info, locator


async def login(page, username: str, password: str) -> dict:
    note: dict = {"ok": False, "captcha": "none"}
    await page.goto(page.url.split("#", 1)[0] or page.url, wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)
    snapshot = await page.evaluate(PAGE_JS)
    note["loginPage"] = {
        "url": snapshot.get("url"),
        "title": snapshot.get("title"),
        "rpaCount": snapshot.get("rpaCount"),
        "inputs": snapshot.get("inputs"),
        "buttons": [item["text"] for item in snapshot.get("buttons") or []][:15],
    }
    await screenshot(page, "01-login")
    account_tab = page.get_by_role("tab", name="账号登录")
    if await account_tab.count():
        await account_tab.first.click()
        await page.wait_for_timeout(300)

    password_box = page.locator("input[type='password']:visible").first
    await password_box.wait_for(state="visible", timeout=15000)
    user_box = page.locator("input[placeholder='账号或手机号码']:visible").first
    await user_box.fill(username)
    await password_box.fill(password)

    # 必须勾选「我已阅读并同意《用户注册协议》」
    note["agreement"] = False
    try:
        agreed = await page.evaluate(
            """() => {
              const labels = [...document.querySelectorAll('label, .el-checkbox')];
              const target = labels.find((el) => (el.innerText || '').includes('用户注册协议'));
              if (!target) return { found: false };
              const input = target.querySelector('input[type="checkbox"]')
                || target.closest('.el-checkbox')?.querySelector('input[type="checkbox"]')
                || document.querySelector('.el-checkbox input[type="checkbox"]');
              if (!input) return { found: true, checked: false, noInput: true };
              if (!input.checked) {
                const clickable = target.querySelector('.el-checkbox__inner') || target;
                clickable.click();
              }
              return { found: true, checked: !!input.checked };
            }"""
        )
        note["agreement"] = agreed
        if not (isinstance(agreed, dict) and agreed.get("checked")):
            # fallback: click visible checkbox near agreement text
            box = page.locator(".el-checkbox:visible").filter(has_text="用户注册协议").first
            if await box.count():
                await box.click()
                note["agreement"] = {"found": True, "checked": True, "via": "locator"}
    except Exception as exc:
        note["agreement"] = {"error": type(exc).__name__}

    captcha_input = page.locator("input[placeholder='验证码']:visible").first
    if await captcha_input.count():
        note["captcha"] = "present"
        code = os.environ.get("PROBE_CAPTCHA_CODE", "").strip() or None
        try:
            info, captcha_img = await resolve_captcha_image(page)
            note["captchaDom"] = info
            # data-URL 已写出 login-captcha.png；仅在缺失时再截图
            if not (isinstance(info, dict) and info.get("fromDataUrl")):
                handle = await captcha_img.element_handle() if await captcha_img.count() else None
                if handle:
                    image_bytes = await handle.screenshot()
                    (SCREEN_DIR / "login-captcha.png").write_bytes(image_bytes)
                    note["captchaBytes"] = len(image_bytes)
            else:
                note["captchaBytes"] = info.get("bytes")
            if not code:
                raw = (SCREEN_DIR / "login-captcha.png").read_bytes() if (SCREEN_DIR / "login-captcha.png").exists() else b""
                if raw:
                    code = try_ocr(raw)
        except Exception as exc:
            note["captchaError"] = type(exc).__name__
        if code:
            await captcha_input.fill(code)
            note["captcha"] = "filled"
            note["captchaLen"] = len(code)
        else:
            await screenshot(page, "01-login-captcha")
            code = await wait_for_human_captcha_code(180)
            if code:
                await captcha_input.fill(code)
                note["captcha"] = "file"
                note["captchaLen"] = len(code)
            else:
                note["captcha"] = "unresolved"
                if os.environ.get("PROBE_PAUSE_ON_CAPTCHA") == "1":
                    await page.pause()
                else:
                    return note

    # 再确认协议已勾选，避免未勾选导致登录按钮无效
    try:
        await page.evaluate(
            """() => {
              const labels = [...document.querySelectorAll('label, .el-checkbox')];
              const target = labels.find((el) => (el.innerText || '').includes('用户注册协议'));
              const input = target?.querySelector('input[type="checkbox"]')
                || document.querySelector('.el-checkbox input[type="checkbox"]');
              if (input && !input.checked) {
                (target?.querySelector('.el-checkbox__inner') || target || input).click();
              }
            }"""
        )
    except Exception:
        pass

    login_btn = page.locator("button.el-button--primary:has-text('登录'):visible").first
    if await login_btn.count() == 0:
        login_btn = page.get_by_role("button", name="登录")
    await login_btn.click()
    try:
        await page.wait_for_function(
            "() => !location.href.toLowerCase().includes('login') || document.querySelector('.el-menu, .sidebar, .layout')",
            timeout=20000,
        )
        note["ok"] = True
    except PlaywrightTimeoutError:
        error = page.locator(".el-message--error, .ant-message-error, .el-form-item__error")
        if await error.count():
            note["error"] = (await error.first.inner_text())[:200]
        else:
            note["error"] = "login_timeout"
        await screenshot(page, "01-login-failed")
        # 默认不自动重试，避免密码/验证码错误导致锁号；仅显式 PROBE_CAPTCHA_RETRY=1 才重试一次
        if note.get("captcha") in {"file", "filled"} and os.environ.get("PROBE_CAPTCHA_RETRY", "0") == "1":
            note["retry"] = True
            try:
                await page.locator("img.login_img:visible").first.click()
                await page.wait_for_timeout(800)
            except Exception:
                pass
            info2, _captcha_img2 = await resolve_captcha_image(page)
            note["captchaDomRetry"] = info2
            code2 = await wait_for_human_captcha_code(180)
            if code2 and await captcha_input.count():
                await captcha_input.fill("")
                await captcha_input.fill(code2)
                await login_btn.click()
                try:
                    await page.wait_for_function(
                        "() => !location.href.toLowerCase().includes('login') || document.querySelector('.el-menu, .sidebar, .layout')",
                        timeout=20000,
                    )
                    note["ok"] = True
                    note["captcha"] = "file_retry"
                    note.pop("error", None)
                except PlaywrightTimeoutError:
                    if await error.count():
                        note["error"] = (await error.first.inner_text())[:200]
                    await screenshot(page, "01-login-failed-retry")
                    return note
            else:
                return note
        else:
            return note
    await page.wait_for_timeout(1500)
    await screenshot(page, "02-after-login")
    note["after"] = await page.evaluate(PAGE_JS)
    return note


async def probe_section(page, name: str, menu_texts: tuple[str, ...], hashes: tuple[str, ...]) -> dict:
    portal_root = page.url.split("#", 1)[0].rstrip("/")
    clicked = await safe_click_text(page, menu_texts)
    if not clicked:
        for hash_path in hashes:
            await page.goto(f"{portal_root}/#{hash_path.lstrip('#')}", wait_until="domcontentloaded")
            await page.wait_for_timeout(1600)
            snap = await page.evaluate(PAGE_JS)
            if snap.get("tables") or "login" not in str(snap.get("url") or "").lower():
                clicked = f"hash:{hash_path}"
                break
    else:
        await page.wait_for_timeout(800)
    await click_query_if_present(page)
    await screenshot(page, name)
    page_snap = await page.evaluate(PAGE_JS)
    rows = await page.evaluate(ROWS_JS)
    return {
        "navigatedBy": clicked,
        "page": page_snap,
        "rows": rows,
    }


COLLECT_BY_HEADERS_JS = r"""() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const tables = [...document.querySelectorAll('.el-table')];
  if (!tables.length) return { error: 'no_el_table' };
  const table = tables
    .map((candidate) => ({
      candidate,
      rowCount: candidate.querySelectorAll('.el-table__body-wrapper tbody tr').length,
    }))
    .sort((a, b) => b.rowCount - a.rowCount)[0].candidate;
  const headers = [...table.querySelectorAll('.el-table__header-wrapper th')]
    .map((header) => clean(header.textContent));
  const indexOfAny = (...names) => {
    for (const name of names) {
      const exact = headers.indexOf(name);
      if (exact >= 0) return exact;
    }
    for (const name of names) {
      const fuzzy = headers.findIndex((header) => header.includes(name));
      if (fuzzy >= 0) return fuzzy;
    }
    return -1;
  };
  const idx = {
    poNo: indexOfAny('订单编号', '采购单号'),
    orderDate: indexOfAny('日期'),
    orderType: indexOfAny('订单类型'),
    totalAmount: indexOfAny('总金额(元)', '总金额'),
    replyStatus: indexOfAny('回复状态'),
    deliveryStatus: indexOfAny('交货状态', '发货状态'),
    orgName: indexOfAny('所属单位', '供应商单位', '主体'),
  };
  if (idx.poNo < 0 || idx.replyStatus < 0) {
    return { error: 'required_headers_missing', headers, idx };
  }
  const rows = [];
  for (const row of table.querySelectorAll('.el-table__body-wrapper tbody tr')) {
    const cells = [...row.querySelectorAll(':scope > td')];
    const cell = (i) => (i >= 0 && i < cells.length ? clean(cells[i].textContent) : '');
    const poNo = cell(idx.poNo);
    if (!poNo || poNo === '--') continue;
    rows.push({
      poNo,
      orderDate: cell(idx.orderDate),
      orderType: cell(idx.orderType),
      totalAmount: cell(idx.totalAmount),
      replyStatus: cell(idx.replyStatus),
      deliveryStatus: cell(idx.deliveryStatus),
      orgName: cell(idx.orgName),
    });
  }
  return { headers, idx, rowCount: rows.length, rows };
}"""

DETAIL_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
  const buttons = [...document.querySelectorAll('button, .el-button, a.el-link, .el-link')].map((btn) => ({
    text: clean(btn.innerText || btn.getAttribute('aria-label') || ''),
    disabled: !!(btn.disabled || btn.getAttribute('disabled') || String(btn.className || '').includes('is-disabled')),
  })).filter((item) => item.text).slice(0, 80);
  const dateInputs = [...document.querySelectorAll('input')].filter(visible).map((el) => ({
    placeholder: el.placeholder || '',
    value: el.value || '',
    disabled: !!el.disabled,
    readonly: !!el.readOnly,
    className: String(el.className || '').slice(0, 80),
  })).filter((item) => (
    item.placeholder.includes('日期')
    || item.placeholder.includes('交货')
    || item.className.includes('el-date')
    || /^\d{4}-\d{2}-\d{2}$/.test(item.value)
  )).slice(0, 20);
  const tables = [...document.querySelectorAll('.el-table')].map((table) => {
    const headers = [...table.querySelectorAll('.el-table__header-wrapper th')].map((th) => clean(th.innerText));
    const rowCount = table.querySelectorAll('.el-table__body-wrapper tbody tr').length;
    return { headers, rowCount };
  }).filter((item) => item.headers.length || item.rowCount).slice(0, 6);
  const tags = [...document.querySelectorAll('.el-tag')].map((el) => clean(el.innerText)).filter(Boolean).slice(0, 20);
  return {
    url: location.href,
    hash: location.hash,
    title: document.title,
    rpaCount: document.querySelectorAll('[data-rpa]').length,
    tags,
    buttons,
    dateInputs,
    tables,
    hasSave: buttons.some((b) => b.text.includes('保存')),
    hasSign: buttons.some((b) => b.text.includes('签章')),
  };
}"""


async def probe_assumed_po_detail(page, assumed_po: str) -> dict:
    """打开演练样例「详情」。只读交期/签章控件，不点保存/签章。"""
    note: dict = {"poNo": assumed_po, "opened": False}
    row = page.locator(".el-table__body-wrapper tbody tr").filter(has_text=assumed_po).first
    if await row.count() == 0:
        note["reason"] = "row_not_found"
        return note
    detail = row.get_by_text("详情", exact=True).first
    if await detail.count() == 0:
        note["reason"] = "detail_link_missing"
        return note
    await detail.click(timeout=4000)
    await page.wait_for_timeout(1800)
    await screenshot(page, "07-assumed-po-detail")
    snap = await page.evaluate(DETAIL_JS)
    note["opened"] = "login" not in str(snap.get("hash") or "").lower()
    note["page"] = snap
    note["writeButtonsPresent"] = {
        "save": bool(snap.get("hasSave")),
        "sign": bool(snap.get("hasSign")),
    }
    return note


FORM_FILTERS_JS = r"""() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const items = [...document.querySelectorAll('.el-form-item')].slice(0, 24).map((item) => ({
    label: clean(item.querySelector('.el-form-item__label')?.innerText),
    placeholders: [...item.querySelectorAll('input')].map((el) => el.placeholder || ''),
    values: [...item.querySelectorAll('input')].map((el) => el.value || ''),
  }));
  return items.filter((item) => item.label || item.placeholders.some(Boolean));
}"""


def count_pending_sign(rows: dict) -> int:
    total = 0
    for row in rows.get("rows") or []:
        blob = " ".join(str(value) for value in row.values())
        if "待签章" in blob:
            total += 1
    return total


async def collect_orders_by_headers(page) -> dict:
    """不依赖 data-rpa：用表头文字读订单列表（对齐扫单 Flow）。"""
    return await page.evaluate(COLLECT_BY_HEADERS_JS)


async def select_form_option(page, label: str, option: str) -> str | None:
    opened = await page.evaluate(
        """(labelText) => {
          const clean = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
          const items = [...document.querySelectorAll('.el-form-item')];
          const item = items.find((el) => {
            const text = clean(el.querySelector('.el-form-item__label')?.innerText);
            return text === labelText || text.startsWith(labelText);
          });
          if (!item) return false;
          const trigger = item.querySelector('.el-select input, .el-input__inner, input');
          if (!trigger) return false;
          trigger.click();
          return true;
        }""",
        label,
    )
    if not opened:
        return None
    await page.wait_for_timeout(500)
    option_loc = page.locator(".el-select-dropdown:visible li, .el-select-dropdown:visible .el-option").filter(
        has_text=option
    ).first
    try:
        await option_loc.click(timeout=4000)
        await page.wait_for_timeout(400)
        return option
    except Exception:
        await page.keyboard.press("Escape")
        return None


async def fill_form_input(page, label: str, value: str) -> bool:
    item = page.locator(".el-form-item").filter(has_text=label).first
    if await item.count() == 0:
        return False
    box = item.locator("input:visible").first
    try:
        await box.fill(value, timeout=3000)
        return True
    except Exception:
        return False


async def probe_scan_label_capability(page, *, assumed_po: str) -> dict:
    """先按「回复状态=待签章」筛选验证读标签；再定位演练用真实 PO（不改 SRM 状态）。"""
    note: dict = {"assumedPendingPo": assumed_po, "dataRpaRequired": False}
    note["filters"] = await page.evaluate(FORM_FILTERS_JS)
    note["unfiltered"] = await collect_orders_by_headers(page)
    note["unfilteredPendingCount"] = sum(
        1
        for row in note["unfiltered"].get("rows") or []
        if str(row.get("replyStatus") or "").strip() == "待签章"
    )
    selected = None
    skip_filter = os.environ.get("PROBE_SKIP_PENDING_FILTER", "0") == "1"
    if not skip_filter:
        selected = await select_form_option(page, "回复状态", "待签章")
        note["filterSelected"] = selected
        queried = False
        if selected:
            queried = await click_query_if_present(page)
        note["filterQueried"] = queried
        await screenshot(page, "03b-orders-pending-filter")
        note["filtered"] = await collect_orders_by_headers(page)
        note["filteredPendingCount"] = sum(
            1
            for row in note["filtered"].get("rows") or []
            if str(row.get("replyStatus") or "").strip() == "待签章"
        )
    else:
        note["filterSelected"] = "skipped"
        note["filterQueried"] = False
        note["filteredPendingCount"] = None
    await fill_form_input(page, "订单编号", assumed_po)
    await click_query_if_present(page)
    await screenshot(page, "03c-orders-assumed-po")
    located = await collect_orders_by_headers(page)
    match = next(
        (
            row
            for row in located.get("rows") or []
            if str(row.get("poNo") or "").upper() == assumed_po.upper()
        ),
        None,
    )
    note["assumedPoLookup"] = located
    note["assumedPoRow"] = match
    headers_ok = (
        note["unfiltered"].get("error") is None
        and int((note["unfiltered"].get("idx") or {}).get("replyStatus") or -1) >= 0
        and int((note["unfiltered"].get("idx") or {}).get("poNo") or -1) >= 0
    )
    note["headersOk"] = headers_ok
    note["ok"] = headers_ok and match is not None
    if match is not None:
        note["detail"] = await probe_assumed_po_detail(page, assumed_po)
    else:
        note["detail"] = {"opened": False, "reason": "assumed_po_missing"}
    return note



def find_unchecked(rows: dict) -> dict | None:
    for row in rows.get("rows") or []:
        blob = " ".join(str(value) for value in row.values())
        if "未对账" in blob:
            date_value = ""
            amount_value = ""
            for key, value in row.items():
                if key.startswith("_"):
                    continue
                if "日期" in key and not date_value:
                    date_value = str(value)
                if "额" in key and not amount_value:
                    amount_value = str(value)
            return {
                "checkDate": date_value,
                "checkAmount": amount_value,
                "buttons": row.get("_buttons") or [],
            }
    return None


async def open_payable_readonly(page, recon: dict) -> dict:
    clicked = await safe_click_text(page, ("收货应付", "明细", "详情"), timeout=3000)
    if not clicked:
        return {"opened": False, "reason": "no_safe_detail_button"}
    await page.wait_for_timeout(1500)
    await screenshot(page, "06-payable-detail")
    return {
        "opened": True,
        "clicked": clicked,
        "page": await page.evaluate(PAGE_JS),
        "from": recon.get("uncheckedStatement"),
    }


async def launch_browser(playwright, headless: bool):
    requested = os.environ.get("PROBE_BROWSER_CHANNEL", "").strip().lower()
    if requested in {"", "chromium", "bundled"}:
        requested_channel = None
    else:
        requested_channel = requested
    candidates: list[str | None] = [requested_channel]
    for item in (None, "chromium-headless-shell", "msedge", "chrome"):
        if item not in candidates:
            candidates.append(item)
    last_error: Exception | None = None
    for channel in candidates:
        kwargs: dict = {"headless": headless}
        if channel:
            kwargs["channel"] = channel
        browser = None
        try:
            browser = await playwright.chromium.launch(**kwargs)
            context = await browser.new_context(viewport={"width": 1600, "height": 1000})
            page = await context.new_page()
            return browser, context, page, channel or "chromium"
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f"launch_failed channel={channel or 'bundled'} err={exc}")
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"browser launch failed: {last_error}") from last_error


async def main() -> int:
    portal_url, username, password = load_credentials()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    blocked: list[dict] = []
    seen_writes: list[dict] = []
    headless = os.environ.get("PROBE_HEADLESS", "0") == "1"

    async with async_playwright() as playwright:
        browser, context, page, browser_label = await launch_browser(playwright, headless)
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
        print(f"browser={browser_label} headless={headless}")

        async def on_route(route):
            request = route.request
            method = request.method.upper()
            url = request.url
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                seen_writes.append({"method": method, "url": redact_url(url)})
            if should_block_probe_write(method, url):
                blocked.append({"method": method, "url": redact_url(url)})
                await route.abort("blockedbyclient")
                return
            await route.continue_()

        await page.route("**/*", on_route)
        await page.goto(portal_url, wait_until="domcontentloaded")
        login_info = await login(page, username, password)
        result = {
            "probedAt": datetime.now(UTC).isoformat(),
            "portalUrl": portal_url,
            "username": username,
            "browser": browser_label,
            "headless": headless,
            "writeGuard": "abort save/sign/generate/submit/delete; allow login+query",
            "forbiddenClicks": list(FORBIDDEN_CLICK) + sorted(FORBIDDEN_CLICK_EXACT),
            "login": login_info,
        }
        if not login_info.get("ok"):
            result["blockedRequests"] = blocked
            result["writeLikeRequests"] = seen_writes[:40]
            OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print("login=failed")
            print(f"wrote {OUT_JSON}")
            await browser.close()
            return 3

        result["home"] = await page.evaluate(PAGE_JS)
        result["orderList"] = await probe_section(
            page,
            "03-orders",
            ("订单", "采购订单", "订单管理", "待签章"),
            ("/supplier/orders", "/order", "/orders", "/po", "/order/list"),
        )
        result["pendingSignCount"] = count_pending_sign(result["orderList"].get("rows") or {})
        assumed_po = os.environ.get("PROBE_ASSUMED_PENDING_PO", "POJS2607170008").strip()
        result["scanLabels"] = await probe_scan_label_capability(page, assumed_po=assumed_po)
        scan_only = os.environ.get("PROBE_SCAN_ONLY", "0") == "1"
        if scan_only:
            result["receiptList"] = {"skipped": True}
            result["reconciliationList"] = {"skipped": True}
            result["uncheckedStatement"] = None
            result["payableDetail"] = {"opened": False, "reason": "scan_only"}
            unchecked = None
        else:
            result["receiptList"] = await probe_section(
                page,
                "04-receipts",
                ("收货", "收货列表", "入库"),
                ("/supplier/receivings", "/receiving", "/receipt", "/asn"),
            )
            result["reconciliationList"] = await probe_section(
                page,
                "05-reconciliation",
                ("对账", "对账单", "财务对账"),
                ("/finance/reconciliation", "/reconciliation", "/check"),
            )
            unchecked = find_unchecked(result["reconciliationList"].get("rows") or {})
            result["uncheckedStatement"] = unchecked
            if unchecked:
                result["payableDetail"] = await open_payable_readonly(page, result)
            else:
                result["payableDetail"] = {"opened": False, "reason": "no_unchecked_row"}

        result["blockedRequests"] = blocked
        result["writeLikeRequests"] = seen_writes[:60]
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("login=ok")
        print(f"pendingSignCount={result['pendingSignCount']}")
        print(f"scanLabelsOk={result['scanLabels'].get('ok')}")
        print(f"filteredPending={result['scanLabels'].get('filteredPendingCount')}")
        assumed_row = result["scanLabels"].get("assumedPoRow") or {}
        print(f"assumedPo={assumed_po} actualReply={assumed_row.get('replyStatus')}")
        detail = (result.get("scanLabels") or {}).get("detail") or {}
        print(f"detailOpened={detail.get('opened')} hasSave={detail.get('writeButtonsPresent', {}).get('save')} hasSign={detail.get('writeButtonsPresent', {}).get('sign')}")
        if not scan_only:
            print(f"receiptRows={result['receiptList'].get('rows', {}).get('rowCount')}")
            print(f"reconRows={result['reconciliationList'].get('rows', {}).get('rowCount')}")
            print(f"unchecked={bool(unchecked)}")
        print(f"blockedWrites={len(blocked)}")
        print(f"wrote {OUT_JSON}")
        await browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
