import re
from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaHumanRequiredError,
    RpaRetryableError,
    login_official_srm,
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
PENDING_REPLY_STATUS = "待签章"
OUTPUT_SCHEMA_VERSION = "SRM_PENDING_ORDERS_OUTPUT_V1"
MAX_PAGES = 50

COLLECT_ORDERS_JS = r"""() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const page = document.querySelector("[data-rpa='order-list-page']");
  if (!page) return null;
  // Prefer the main list table (largest body); Element UI may render fixed clones.
  const tables = [...page.querySelectorAll('.el-table')];
  if (!tables.length) return null;
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
  // Demo portal uses 订单编号; keep 采购单号 as alias for older mocks.
  const idx = {
    poNo: indexOfAny('订单编号', '采购单号'),
    orderDate: indexOfAny('日期'),
    orderType: indexOfAny('订单类型'),
    totalAmount: indexOfAny('总金额(元)', '总金额'),
    replyStatus: indexOfAny('回复状态'),
    deliveryStatus: indexOfAny('交货状态', '发货状态'),
    supplierName: indexOfAny('供应商单位', '主体'),
  };
  if (idx.poNo < 0 || idx.replyStatus < 0) {
    return { error: 'required_headers_missing', headers };
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
      supplierName: cell(idx.supplierName),
    });
  }
  return rows;
}"""


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_captcha_code(image_src):
    if not isinstance(image_src, str) or not image_src.strip():
        return None
    clean_src = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean_src.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


def filter_pending_orders(raw_rows):
    """提取待签章订单；行数据异常时抛出业务错误。"""
    if not isinstance(raw_rows, list):
        raise RpaBusinessError(
            "ORDER_LIST_UNAVAILABLE",
            "Supplier portal order list could not be read",
        )
    orders = []
    seen = set()
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        po_no = _clean(raw.get("poNo")).upper()
        if not po_no or po_no in seen:
            continue
        seen.add(po_no)
        if _clean(raw.get("replyStatus")) != PENDING_REPLY_STATUS:
            continue
        orders.append(
            {
                "poNo": po_no,
                "orderDate": _clean(raw.get("orderDate")),
                "orderType": _clean(raw.get("orderType")),
                "totalAmount": _clean(raw.get("totalAmount")),
                "replyStatus": PENDING_REPLY_STATUS,
                "deliveryStatus": _clean(raw.get("deliveryStatus")),
                "supplierName": _clean(raw.get("supplierName")),
            }
        )
    return orders


async def _safe_emit(ctx, event_type, *, level="INFO", message, payload=None):
    try:
        await ctx.events.emit(event_type, level=level, message=message, payload=payload)
    except Exception:
        return


async def _safe_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return


class SupplierPortalScanAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.page
        self.selectors = ctx.selectors

    def selector(self, name, **values):
        value = self.selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError(
                "FLOW_SELECTOR_MISSING",
                f"Required supplier portal selector is missing: {name}",
            )
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    async def login(self):
        await login_official_srm(self.ctx, selector=self.selector)

    async def _wait_for_login_result(self):
        success = self.page.locator(self.selector("login_success"))
        error = self.page.locator(self.selector("login_error"))
        for _ in range(50):
            if await success.is_visible():
                return
            if await error.is_visible():
                await self._redact_login_fields()
                raise RpaBusinessError(
                    "SRM_LOGIN_FAILED",
                    "Supplier portal login failed",
                )
            await self.page.wait_for_timeout(200)
        await self._redact_login_fields()
        raise RpaRetryableError(
            "SRM_LOGIN_TIMEOUT",
            "Supplier portal login did not complete in time",
        )

    async def _redact_login_fields(self):
        for name in ("username", "password", "captcha"):
            try:
                await self.page.fill(self.selector(name), "")
            except Exception:
                continue

    async def open_order_list(self):
        step_id = "srm.open_order_list"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Opening supplier portal order list",
            payload={"stepId": step_id, "stepType": step_id},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        try:
            await self.page.goto(f"{portal_root}/#/supplier/orders", wait_until="domcontentloaded")
            await self.page.locator(self.selector("order_page")).wait_for(
                state="visible", timeout=10000
            )
            await self._wait_loading_done()
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_LIST_UNAVAILABLE",
                "Supplier portal order list could not be opened",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Supplier portal order list opened",
            payload={"stepId": step_id},
        )

    async def _wait_loading_done(self):
        try:
            await self.page.locator(self.selector("loading_mask")).wait_for(
                state="hidden", timeout=15000
            )
        except Exception:
            pass

    async def collect_page_rows(self):
        try:
            await self._wait_loading_done()
            result = await self.page.evaluate(COLLECT_ORDERS_JS)
            if result is None:
                raise RpaBusinessError(
                    "ORDER_LIST_UNAVAILABLE",
                    "Supplier portal order list table is missing",
                )
            if isinstance(result, dict) and result.get("error"):
                raise RpaBusinessError(
                    "ORDER_LIST_UNAVAILABLE",
                    f"Supplier portal order list headers unavailable: {result.get('headers')}",
                )
            return result
        except RpaBusinessError:
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_LIST_UNAVAILABLE",
                "Supplier portal order list could not be read",
            ) from exc

    async def collect_all_rows(self):
        rows = []
        for _ in range(MAX_PAGES):
            rows.extend(await self.collect_page_rows())
            next_button = self.page.locator(self.selector("next_page"))
            try:
                if not await next_button.is_visible() or not await next_button.is_enabled():
                    break
                await next_button.click()
                await self.page.wait_for_timeout(500)
            except Exception:
                break
        return rows


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError(
            "PORTAL_URL_MISSING",
            "Supplier portal URL is unavailable",
        )
    await ctx.log.info("Starting supplier portal pending-order scan Flow")

    adapter = SupplierPortalScanAdapter(ctx)
    await adapter.login()
    await adapter.open_order_list()

    step_id = "srm.scan_pending_orders"
    await ctx.events.emit(
        "STEP_STARTED",
        message="Scanning pending-signature orders",
        payload={"stepId": step_id, "stepType": step_id},
    )
    raw_rows = await adapter.collect_all_rows()
    orders = filter_pending_orders(raw_rows)
    await _safe_screenshot(ctx, "supplier-portal-pending-orders", step_id)
    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Pending-signature orders collected",
        payload={
            "stepId": step_id,
            "totalRows": len(raw_rows),
            "pendingCount": len(orders),
        },
    )
    await ctx.log.info(
        "Supplier portal pending-order scan completed",
        {"totalRows": len(raw_rows), "pendingCount": len(orders)},
    )
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "portalUrl": ctx.portal_url,
        "totalRows": len(raw_rows),
        "orders": orders,
    }
