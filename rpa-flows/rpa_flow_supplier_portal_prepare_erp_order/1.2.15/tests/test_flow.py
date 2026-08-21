import asyncio
import importlib.util
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from xml.sax.saxutils import escape

import httpx
from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaHumanRequiredError,
    RpaRetryableError,
)

FLOW_DIR = Path(__file__).resolve().parents[1]
FLOW_SPEC = importlib.util.spec_from_file_location(
    "supplier_portal_prepare_erp_order_flow_1_2_14",
    FLOW_DIR / "flow.py",
)
if FLOW_SPEC is None or FLOW_SPEC.loader is None:
    raise RuntimeError("Flow module could not be loaded for tests")
flow_module = importlib.util.module_from_spec(FLOW_SPEC)
sys.modules[FLOW_SPEC.name] = flow_module
FLOW_SPEC.loader.exec_module(flow_module)

ERP_TOKEN_URL = "http://erp.test/core/oauth/token"
ERP_ORDER_IMPORT_URL = "http://erp.test/core/api/srm/so/salesOrderImport"
ErpSalesOrderClient = flow_module.ErpSalesOrderClient
_emit_erp_event_safely = flow_module._emit_erp_event_safely
_org_name_from_ctx = flow_module._org_name_from_ctx
build_erp_draft = flow_module.build_erp_draft
parse_order_xlsx = flow_module.parse_order_xlsx
reconcile_attachment_with_portal = flow_module.reconcile_attachment_with_portal
CUSTOMER_NAME = "天地偉業技術有限公司"
ORG_NAME = "深圳市芯云信息科技有限公司"


def make_erp_client(**kwargs):
    values = {
        "token_url": ERP_TOKEN_URL,
        "import_url": ERP_ORDER_IMPORT_URL,
        "client_id": "mock-client-id",
        "client_secret": "mock-client-secret",
    }
    values.update(kwargs)
    return ErpSalesOrderClient(**values)


def run_config(**overrides):
    payload = {
        "erpBaseUrl": "http://erp.test",
        "customerName": CUSTOMER_NAME,
        "businessEntity": ORG_NAME,
    }
    payload.update(overrides)
    return MappingProxyType(payload)


def run_credentials(**overrides):
    payload = {
        "username": "portal-user",
        "password": "secret",
        "erpClientId": "mock-client-id",
        "erpClientSecret": "mock-client-secret",
    }
    payload.update(overrides)
    return MappingProxyType(payload)

HEADERS = [
    "供应商编号",
    "供应商名称",
    "订单编号",
    "订单行号",
    "料号",
    "料品名称",
    "料品规格",
    "物料状态",
    "内码",
    "数量",
    "单位",
    "单价（元）",
    "价税合计（元）",
    "要求交货日期",
    "标准交货日期（天）",
    "是否满足LT",
    "供方交期",
    "欠交数量",
    "备注",
    "直发备注",
]
ROW = [
    "02556",
    "深圳市芯云信息科技有限公司",
    "POJS2606030010",
    "10",
    "1B.30040.020227",
    "芯片-视频编解码",
    "[SSC335]-(B)-QFN88(9x9mm)-sigmastar",
    "A",
    "221316",
    "31200.0",
    "个",
    "22.9448",
    "715877.76",
    "2026-06-24",
    "42",
    "否",
    "2026-08-31",
    "20800.0",
    "",
    "是否中性:否;",
]


def make_row(
    line_number,
    customer_item_number,
    *,
    po_no="POJS2606030010",
    quantity=None,
    unit_price=None,
    request_date=None,
    remarks=None,
):
    row = list(ROW)
    row[2] = po_no
    row[3] = line_number
    row[4] = customer_item_number
    if quantity is not None:
        row[9] = quantity
    if unit_price is not None:
        row[11] = unit_price
    if request_date is not None:
        row[13] = request_date
    if remarks is not None:
        row[18] = remarks
    return row


def make_order_detail(lines=None):
    return {
        "supplierCode": "02556",
        "supplierName": "深圳市芯云信息科技有限公司",
        "lines": lines
        or [
            {
                "lineNumber": "10",
                "customerItemNumber": "1B.30040.020227",
                "orderQuantity": "31200.0",
                "unitSellingPrice": "22.9448",
                "requestDate": "2026-06-24",
            }
        ],
    }


def nested_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(nested_keys(item))
        return keys
    if isinstance(value, list):
        keys = set()
        for item in value:
            keys.update(nested_keys(item))
        return keys
    return set()


def column_name(index):
    result = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def make_xlsx(headers=HEADERS, rows=None):
    rows = rows or [ROW]
    values = []
    indexes = {}
    for value in [*headers, *(item for row in rows for item in row)]:
        text = str(value)
        if text not in indexes:
            indexes[text] = len(values)
            values.append(text)
    shared = "".join(f"<si><t>{escape(value)}</t></si>" for value in values)

    def xml_row(number, row):
        cells = "".join(
            (
                f'<c r="{column_name(index)}{number}" '
                f't="s"><v>{indexes[str(value)]}</v></c>'
            )
            for index, value in enumerate(row)
        )
        return f'<row r="{number}">{cells}</row>'

    sheet_rows = xml_row(1, headers) + "".join(
        xml_row(index + 2, row) for index, row in enumerate(rows)
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{shared}</sst>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<workbook "
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="sheet1" sheetId="1" '
            'r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Relationships "
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{sheet_rows}</sheetData></worksheet>",
        )
    return output.getvalue()


class FakeStableLocator:
    def __init__(self, name, timeline):
        self.name = name
        self.timeline = timeline

    @property
    def first(self):
        return self

    async def wait_for(self, *, state, timeout):  # noqa: ASYNC109
        self.timeline.append(("wait", self.name, state, timeout))


class FakeStablePage:
    def __init__(self, selector_names, timeline):
        self.selector_names = selector_names
        self.timeline = timeline
        self.layouts = ["stable-layout", "stable-layout"]

    def locator(self, selector):
        return FakeStableLocator(self.selector_names[selector], self.timeline)

    async def evaluate(self, script, argument):
        if "document.fonts" in script:
            self.timeline.append(("assets", argument))
            return None
        self.timeline.append(("layout", argument))
        return self.layouts.pop(0)

    async def wait_for_timeout(self, milliseconds):
        self.timeline.append(("timeout", milliseconds))


class RecordingEvents:
    def __init__(self):
        self.items = []

    async def emit(self, event_type, **kwargs):
        self.items.append({"type": event_type, **kwargs})


class FakeNavigationLocator:
    def __init__(self, selector, timeline, *, visible=False):
        self.selector = selector
        self.timeline = timeline
        self.visible = visible

    async def wait_for(self, *, state, timeout):  # noqa: ASYNC109
        self.timeline.append(("wait", self.selector, state, timeout))

    async def is_visible(self):
        self.timeline.append(("visible", self.selector))
        return self.visible

    async def count(self):
        return 1

    async def click(self, timeout=None, force=None):  # noqa: ANN001
        self.timeline.append(("click", self.selector))

    def get_by_text(self, text, exact=False):  # noqa: ANN001
        child = FakeNavigationLocator(f"text={text}", self.timeline, visible=True)
        return child

    def locator(self, selector):  # noqa: ANN001
        return FakeNavigationLocator(selector, self.timeline, visible=self.visible)

    def filter(self, has_text=None):  # noqa: ANN001
        return self

    @property
    def first(self):
        return self


class FakeNavigationPage:
    def __init__(self, timeline, *, authenticated=False):
        self.timeline = timeline
        self.authenticated = authenticated

    async def goto(self, url, *, wait_until):
        self.timeline.append(("goto", url, wait_until))

    def locator(self, selector):
        return FakeNavigationLocator(
            selector,
            self.timeline,
            visible=self.authenticated and selector == "login-success",
        )

    async def fill(self, selector, value):
        self.timeline.append(("fill", selector, value))

    async def click(self, selector):
        self.timeline.append(("click", selector))

    async def evaluate(self, script, argument=None):  # noqa: ANN001
        self.timeline.append(("evaluate", argument))
        return True

    async def wait_for_timeout(self, milliseconds):  # noqa: ANN001
        self.timeline.append(("timeout", milliseconds))

    def get_by_text(self, text, exact=False):  # noqa: ANN001
        return FakeNavigationLocator(f"text={text}", self.timeline, visible=True)


class FakeIdentityTableLocator:
    def __init__(self, timeline):
        self.timeline = timeline

    @property
    def first(self):
        return self

    async def wait_for(self, *, state, timeout):  # noqa: ASYNC109
        self.timeline.append(("wait", state, timeout))


class FakeIdentityPage:
    def __init__(self, raw_lines, timeline):
        self.raw_lines = raw_lines
        self.timeline = timeline

    def locator(self, selector):
        self.timeline.append(("locator", selector))
        return FakeIdentityTableLocator(self.timeline)

    async def evaluate(self, script, selector):
        self.timeline.append(("evaluate", selector))
        return self.raw_lines


class NavigationCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_an_authenticated_browser_session(self):
        timeline = []
        events = RecordingEvents()
        adapter = flow_module.SupplierPortalAdapter(
            SimpleNamespace(
                artifacts=SimpleNamespace(),
                credentials=MappingProxyType(
                    {"username": "portal-user", "password": "secret"}
                ),
                events=events,
                page=FakeNavigationPage(timeline, authenticated=True),
                portal_url="http://portal.test/",
                selectors={
                    "login_success": "login-success",
                    "captcha_image": "captcha-image",
                },
            )
        )

        await adapter.login()

        self.assertEqual(
            timeline,
            [
                ("visible", "captcha-image"),
                ("visible", "login-success"),
            ],
        )
        self.assertEqual(events.items[-1]["type"], "STEP_SUCCEEDED")
        self.assertTrue(events.items[-1]["payload"]["reusedSession"])

    async def test_accepts_the_combined_pending_detail_selector(self):
        timeline = []
        events = RecordingEvents()
        selectors = {
            "order_page": "order-page",
            "po_number": "po-number",
            "search_button": "search",
            "order_row": "row-{po_no}",
            "order_detail": "detail-{po_no}",
            "download_order": "download-order",
            "detail_po_number": "ordinary-{po_no}, pending-{po_no}",
        }
        adapter = flow_module.SupplierPortalAdapter(
            SimpleNamespace(
                events=events,
                page=FakeNavigationPage(timeline),
                portal_url="http://portal.test/#/dashboard",
                selectors=selectors,
            )
        )

        await adapter.open_order_detail("POJS2607130002")

        self.assertIn(("evaluate", "POJS2607130002"), timeline)
        self.assertIn(
            (
                "wait",
                "download-order",
                "visible",
                15000,
            ),
            timeline,
        )
        self.assertEqual(events.items[-1]["type"], "STEP_SUCCEEDED")


class OrderLineIdentityCollectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_first_row_and_preserves_cleaned_portal_order(self):
        timeline = []
        page = FakeIdentityPage(
            [
                {
                    "lineNumber": " 20 ",
                    "customerItemNumber": " 1B.30040.020257 ",
                },
                {
                    "lineNumber": "10",
                    "customerItemNumber": "1B.30040.020262",
                },
            ],
            timeline,
        )
        adapter = flow_module.SupplierPortalAdapter(
            SimpleNamespace(
                page=page,
                selectors={"lines_table": "lines-table"},
            )
        )

        result = await adapter.collect_order_line_identities()

        self.assertEqual(
            result,
            [
                {
                    "lineNumber": "20",
                    "customerItemNumber": "1B.30040.020257",
                },
                {
                    "lineNumber": "10",
                    "customerItemNumber": "1B.30040.020262",
                },
            ],
        )
        self.assertEqual(
            timeline,
            [
                ("locator", "lines-table"),
                ("wait", "visible", 10000),
                ("evaluate", "lines-table"),
            ],
        )

    async def test_rejects_unavailable_portal_lines(self):
        adapter = flow_module.SupplierPortalAdapter(
            SimpleNamespace(
                page=FakeIdentityPage([], []),
                selectors={"lines_table": "lines-table"},
            )
        )

        with self.assertRaises(RpaBusinessError) as captured:
            await adapter.collect_order_line_identities()

        self.assertEqual(captured.exception.code, "ORDER_DETAIL_LINES_UNAVAILABLE")


class PackageContractTests(unittest.TestCase):
    def test_manifest_and_selectors_describe_1_2_6_reconciliation(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        selectors = json.loads(
            (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["version"], "1.2.15")
        self.assertIn("Official Portal", manifest["name"])
        selector_blob = json.dumps(selectors, ensure_ascii=False)
        self.assertNotIn("data-rpa", selector_blob)
        self.assertIn("账号或手机号码", selectors["username"])
        self.assertIn("userAgree", selectors["agreement"])
        self.assertIn("订单", selectors["login_success"])
        self.assertEqual(selectors["order_page"], ".el-table")
        self.assertIn("订单编号", selectors["po_number"])
        self.assertIn("导出订单明细", selectors["download_order"])
        self.assertNotIn("下载订单", selectors["download_order"])
        self.assertEqual(selectors["detail_page"], "#app")
        self.assertEqual(selectors["lines_table"], ".el-table")
        source = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertNotIn("ORDER_ATTACHMENT_PO_MISMATCH", source)
        self.assertIn("ORDER_ATTACHMENT_RECONCILED", source)
        self.assertIn("reconcile_attachment_with_portal", source)
        self.assertIn('self.selector("lines_table")', source)
        self.assertIn("textContent", source)


class DetailStabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_stable_detail_before_final_settle(self):
        timeline = []
        selectors = {
            "download_dialog": "dialog",
            "detail_page": "detail",
            "download_order": "download",
            "lines_table": "lines-table",
            "loading_mask": "loading",
        }
        page = FakeStablePage(
            {value: key for key, value in selectors.items()},
            timeline,
        )
        adapter = flow_module.SupplierPortalAdapter(
            SimpleNamespace(page=page, selectors=selectors)
        )

        await adapter.wait_for_detail_stable()

        self.assertEqual(
            timeline,
            [
                ("wait", "download_dialog", "hidden", 10000),
                ("wait", "detail_page", "visible", 10000),
                ("wait", "download_order", "visible", 10000),
                ("wait", "lines_table", "visible", 10000),
                ("wait", "loading_mask", "hidden", 10000),
                ("assets", "detail"),
                (
                    "layout",
                    {
                        "detailSelector": "detail",
                        "rowSelector": "lines-table .el-table__body-wrapper tbody tr",
                    },
                ),
                ("timeout", 150),
                (
                    "layout",
                    {
                        "detailSelector": "detail",
                        "rowSelector": "lines-table .el-table__body-wrapper tbody tr",
                    },
                ),
                ("timeout", 300),
            ],
        )

    async def test_prepare_waits_for_stability_before_screenshot(self):
        timeline = []
        attachment = parse_order_xlsx(make_xlsx())

        class FakeAdapter:
            def __init__(self, _ctx):
                pass

            async def login(self):
                timeline.append("login")

            async def open_order_detail(self, _po_no):
                timeline.append("detail")

            async def collect_order_line_identities(self):
                timeline.append("collect")
                return [
                    {
                        "lineNumber": "10",
                        "customerItemNumber": "1B.30040.020227",
                    }
                ]

            async def download_order(self):
                timeline.append("download")
                return attachment

            async def wait_for_detail_stable(self):
                timeline.append("stable")

        class RecordingLog:
            async def info(self, *_args):
                timeline.append("log")

        class RecordingArtifacts:
            async def screenshot(self, name, *, step_id):
                timeline.append(("screenshot", name, step_id))

        class RecordingEvents:
            async def emit(self, event_type, **_kwargs):
                timeline.append(("event", event_type))

        original_adapter = flow_module.SupplierPortalAdapter
        flow_module.SupplierPortalAdapter = FakeAdapter
        try:
            result = await flow_module._prepare_erp_order(
                SimpleNamespace(
                    portal_url="http://portal.test/",
                    input=MappingProxyType({"po_no": "POJS2606030010"}),
                    config=run_config(),
                    credentials=run_credentials(),
                    log=RecordingLog(),
                    artifacts=RecordingArtifacts(),
                    events=RecordingEvents(),
                )
            )
        finally:
            flow_module.SupplierPortalAdapter = original_adapter

        self.assertLess(timeline.index("detail"), timeline.index("collect"))
        self.assertLess(timeline.index("collect"), timeline.index("download"))
        self.assertLess(timeline.index("download"), timeline.index("stable"))
        self.assertEqual(result["orderDetail"]["lines"][0]["poNo"], "POJS2606030010")
        self.assertIn(("event", "ORDER_ATTACHMENT_RECONCILED"), timeline)
        self.assertLess(
            timeline.index("stable"),
            timeline.index(
                (
                    "screenshot",
                    "supplier-portal-erp-draft-prepared",
                    "erp.prepare",
                )
            ),
        )


class ErpSalesOrderClientTests(unittest.IsolatedAsyncioTestCase):
    def payload(self):
        attachment = parse_order_xlsx(make_xlsx())
        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
            customer_name=CUSTOMER_NAME,
            org_name=ORG_NAME,
        )
        return payload

    @staticmethod
    def token_response():
        return {
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 2999,
            "scope": "read write trust",
            "jti": "mock-jti",
        }

    @staticmethod
    def success_response():
        return {
            "code": "2000",
            "message": "导入处理完成.",
            "rows": [
                {
                    "orderNumber": "10108260700027",
                    "sourceHeaderId": "mock-source-header",
                    "headerId": "1091975",
                    "soStatus": "BOOKED",
                    "soApprovedStatus": "NEW",
                    "processGroupId": "1784172232212",
                    "processStatusCode": "COMPLETE",
                    "processMessage": "not exposed",
                }
            ],
            "success": True,
            "total": 1,
        }

    @staticmethod
    def row_error_response(process_message=None):
        return {
            "code": "2000",
            "message": "导入处理完成.",
            "rows": [
                {
                    "orderNumber": None,
                    "sourceHeaderId": None,
                    "headerId": None,
                    "soStatus": None,
                    "soApprovedStatus": None,
                    "processGroupId": "1784777664704",
                    "processStatusCode": "ERROR",
                    "processMessage": process_message
                    or "1.系统中查找客户料号&物料编码出错！请联系系统管理员. ",
                }
            ],
            "success": True,
            "total": 1,
        }

    async def test_posts_token_query_and_exact_erp_payload(self):
        requests = []

        def handler(request):
            requests.append(request)
            if str(request.url).startswith(ERP_TOKEN_URL):
                return httpx.Response(200, json=self.token_response())
            self.assertEqual(str(request.url), ERP_ORDER_IMPORT_URL)
            return httpx.Response(200, json=self.success_response())

        payload = self.payload()
        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            token_type, access_token = await client.fetch_access_token()
            result = await client.import_sales_order(
                payload,
                token_type,
                access_token,
            )

        self.assertEqual(len(requests), 2)
        token_request, import_request = requests
        self.assertEqual(token_request.method, "POST")
        self.assertEqual(
            token_request.url.params.get("grant_type"),
            "client_credentials",
        )
        self.assertEqual(token_request.url.params.get("client_id"), "mock-client-id")
        self.assertEqual(
            token_request.url.params.get("client_secret"),
            "mock-client-secret",
        )
        self.assertEqual(import_request.method, "POST")
        self.assertEqual(
            import_request.headers["Authorization"],
            "bearer mock-access-token",
        )
        self.assertTrue(
            import_request.headers["Content-Type"].startswith("application/json")
        )
        self.assertNotIn("mock-access-token", str(import_request.url))
        self.assertEqual(json.loads(import_request.content), payload)
        self.assertEqual(result["code"], "2000")
        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["rows"][0]["orderNumber"], "10108260700027")
        self.assertEqual(result["rows"][0]["processMessage"], "not exposed")

    async def test_rejects_unfilled_credential_placeholders(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=self.token_response())

        async with make_erp_client(
            client_id="__FILL_ERP_CLIENT_ID__",
            client_secret="__FILL_ERP_CLIENT_SECRET__",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaFatalError) as captured:
                await client.fetch_access_token()

        self.assertEqual(captured.exception.code, "ERP_CREDENTIALS_NOT_CONFIGURED")
        self.assertEqual(calls, [])

    async def test_token_service_failure_is_retryable_before_import(self):
        secret = "private-client-secret"

        def handler(_request):
            return httpx.Response(503, json={"message": secret})

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret=secret,
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaRetryableError) as captured:
                await client.fetch_access_token()

        self.assertEqual(captured.exception.code, "ERP_TOKEN_SERVICE_UNAVAILABLE")
        self.assertNotIn(secret, str(captured.exception))

    async def test_invalid_token_contract_is_fatal(self):
        def handler(_request):
            return httpx.Response(200, json={"token_type": "bearer"})

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaFatalError) as captured:
                await client.fetch_access_token()

        self.assertEqual(captured.exception.code, "ERP_TOKEN_RESPONSE_INVALID")

    async def test_import_invalid_token_is_fatal(self):
        calls = 0

        def handler(_request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(200, json=self.token_response())
            return httpx.Response(
                401,
                json={
                    "error": "invalid_token",
                    "error_description": "Invalid access token: hidden",
                },
            )

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            token_type, token = await client.fetch_access_token()
            with self.assertRaises(RpaFatalError) as captured:
                await client.import_sales_order(self.payload(), token_type, token)

        self.assertEqual(captured.exception.code, "ERP_ACCESS_TOKEN_INVALID")
        self.assertEqual(calls, 2)

    async def test_import_business_failure_is_not_retryable(self):
        def handler(_request):
            return httpx.Response(
                200,
                json={
                    "code": "2001",
                    "message": "字段校验失败",
                    "success": False,
                    "total": 0,
                    "rows": [],
                },
            )

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaBusinessError) as captured:
                await client.import_sales_order(
                    self.payload(),
                    "bearer",
                    "mock-access-token",
                )

        self.assertEqual(captured.exception.code, "ERP_ORDER_IMPORT_REJECTED")

    async def test_import_row_error_is_business_failure_with_safe_details(self):
        response = self.row_error_response()
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(200, json=response)
        )
        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=transport,
        ) as client:
            with self.assertRaises(RpaBusinessError) as captured:
                await client.import_sales_order(
                    self.payload(),
                    "bearer",
                    "mock-access-token",
                )

        error = captured.exception
        self.assertEqual(error.code, "ERP_ORDER_IMPORT_ROW_FAILED")
        self.assertEqual(
            error.safe_message,
            "1.系统中查找客户料号&物料编码出错！请联系系统管理员.",
        )
        row = error.details["rows"][0]
        self.assertIsNone(row["orderNumber"])
        self.assertIsNone(row["sourceHeaderId"])
        self.assertIsNone(row["headerId"])
        self.assertEqual(row["processStatusCode"], "ERROR")
        self.assertEqual(row["processGroupId"], "1784777664704")
        self.assertEqual(row["processMessage"], error.safe_message)

    async def test_import_row_error_limits_process_message(self):
        response = self.row_error_response("x" * 600)
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(200, json=response)
        )
        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=transport,
        ) as client:
            with self.assertRaises(RpaBusinessError) as captured:
                await client.import_sales_order(
                    self.payload(),
                    "bearer",
                    "mock-access-token",
                )

        self.assertEqual(len(captured.exception.safe_message), 500)
        self.assertEqual(
            len(captured.exception.details["rows"][0]["processMessage"]),
            500,
        )

    async def test_import_requires_complete_rows_with_order_numbers(self):
        cases = (
            [],
            [
                {
                    "orderNumber": None,
                    "processStatusCode": "COMPLETE",
                    "processMessage": None,
                }
            ],
            [
                {
                    "orderNumber": "10108260700027",
                    "processStatusCode": "PROCESSING",
                    "processMessage": None,
                }
            ],
        )
        for rows in cases:
            with self.subTest(rows=rows):
                response = {
                    "code": "2000",
                    "message": "导入处理完成.",
                    "rows": rows,
                    "success": True,
                    "total": 1,
                }
                transport = httpx.MockTransport(
                    lambda _request, value=response: httpx.Response(200, json=value)
                )
                async with make_erp_client(
                    client_id="mock-client-id",
                    client_secret="mock-client-secret",
                    transport=transport,
                ) as client:
                    with self.assertRaises(RpaHumanRequiredError) as captured:
                        await client.import_sales_order(
                            self.payload(),
                            "bearer",
                            "mock-access-token",
                        )

                self.assertEqual(
                    captured.exception.code,
                    "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                )

    def test_success_summary_rejects_multiple_erp_order_numbers(self):
        with self.assertRaises(RpaHumanRequiredError) as captured:
            flow_module._erp_order_number(
                {
                    "rows": [
                        {"orderNumber": "10108260700027"},
                        {"orderNumber": "10108260700028"},
                    ]
                }
            )

        self.assertEqual(
            captured.exception.code,
            "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
        )

    def test_erp_header_id_returns_first_nonempty(self):
        self.assertEqual(
            flow_module._erp_header_id(
                {
                    "rows": [
                        {"orderNumber": "101", "headerId": ""},
                        {"orderNumber": "101", "headerId": "1091975"},
                    ]
                }
            ),
            "1091975",
        )
        self.assertEqual(flow_module._erp_header_id({"rows": []}), "")
        self.assertEqual(flow_module._erp_header_id({}), "")

    async def test_import_read_timeout_requires_human_verification(self):
        def handler(request):
            raise httpx.ReadTimeout("private timeout detail", request=request)

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaHumanRequiredError) as captured:
                await client.import_sales_order(
                    self.payload(),
                    "bearer",
                    "mock-access-token",
                )

        self.assertEqual(
            captured.exception.code,
            "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
        )

    async def test_import_ambiguous_http_status_requires_human(self):
        for status_code in (408, 429, 503):
            with self.subTest(status_code=status_code):
                transport = httpx.MockTransport(
                    lambda _request, status=status_code: httpx.Response(
                        status,
                        json={"message": "outcome unavailable"},
                    )
                )
                async with make_erp_client(
                    client_id="mock-client-id",
                    client_secret="mock-client-secret",
                    transport=transport,
                ) as client:
                    with self.assertRaises(RpaHumanRequiredError) as captured:
                        await client.import_sales_order(
                            self.payload(),
                            "bearer",
                            "mock-access-token",
                        )

                self.assertEqual(
                    captured.exception.code,
                    "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
                )

    async def test_success_event_failure_is_suppressed(self):
        class FailingEvents:
            async def emit(self, *_args, **_kwargs):
                raise RuntimeError("event sink unavailable")

        ctx = SimpleNamespace(events=FailingEvents())
        await _emit_erp_event_safely(
            ctx,
            "ERP_ORDER_IMPORT_SUCCEEDED",
            message="ERP sales order import completed",
            payload={"code": "2000"},
        )

    async def test_token_rejection_is_fatal(self):
        def handler(_request):
            return httpx.Response(401, json={"error": "invalid_client"})

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaFatalError) as captured:
                await client.fetch_access_token()

        self.assertEqual(captured.exception.code, "ERP_TOKEN_REJECTED")

    async def test_import_http_validation_failure_is_business_error(self):
        def handler(_request):
            return httpx.Response(422, json={"message": "invalid payload"})

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaBusinessError) as captured:
                await client.import_sales_order(
                    self.payload(),
                    "bearer",
                    "mock-access-token",
                )

        self.assertEqual(captured.exception.code, "ERP_ORDER_IMPORT_REJECTED")

    async def test_import_endpoint_failure_is_fatal(self):
        def handler(_request):
            return httpx.Response(404, json={"message": "not found"})

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaFatalError) as captured:
                await client.import_sales_order(
                    self.payload(),
                    "bearer",
                    "mock-access-token",
                )

        self.assertEqual(
            captured.exception.code,
            "ERP_ORDER_IMPORT_ENDPOINT_INVALID",
        )

    async def test_import_connect_failure_is_retryable_before_send(self):
        def handler(request):
            raise httpx.ConnectError("private connection detail", request=request)

        async with make_erp_client(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(RpaRetryableError) as captured:
                await client.import_sales_order(
                    self.payload(),
                    "bearer",
                    "mock-access-token",
                )

        self.assertEqual(
            captured.exception.code,
            "ERP_ORDER_IMPORT_CONNECTION_FAILED",
        )

    async def test_import_invalid_success_response_requires_human(self):
        cases = (
            (httpx.Response(200, text="not-json"), RpaHumanRequiredError),
            (
                httpx.Response(
                    200,
                    json={"code": "2000", "success": False, "rows": []},
                ),
                RpaHumanRequiredError,
            ),
            (
                httpx.Response(
                    200,
                    json={"code": "2001", "success": True, "rows": []},
                ),
                RpaHumanRequiredError,
            ),
            (
                httpx.Response(
                    200,
                    json={"code": "unexpected", "success": True, "rows": []},
                ),
                RpaHumanRequiredError,
            ),
        )
        for response, expected in cases:
            with self.subTest(response=response):
                async with make_erp_client(
                    client_id="mock-client-id",
                    client_secret="mock-client-secret",
                    transport=httpx.MockTransport(
                        lambda _request, value=response: value
                    ),
                ) as client:
                    with self.assertRaises(expected):
                        await client.import_sales_order(
                            self.payload(),
                            "bearer",
                            "mock-access-token",
                        )

    async def test_run_submits_once_when_success_event_sink_fails(self):
        payload = self.payload()
        submitted = []
        lines = [
            {
                "lineNumber": "10",
                "customerItemNumber": "1B.30040.020227",
                "itemName": "芯片-视频编解码",
                "orderQuantity": "31200.0",
                "orderQuantityUom": "个",
                "unitSellingPrice": "22.9448",
                "requestDate": "2026-06-24",
            }
        ]

        async def prepare(_ctx):
            return {
                "draftOnly": True,
                "transmitted": False,
                "orderDetail": {
                    "supplierCode": "02556",
                    "supplierName": "深圳市芯云信息科技有限公司",
                    "lines": lines,
                },
                "erpPayload": payload,
            }

        class FakeErpClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def fetch_access_token(self):
                return "bearer", "mock-access-token"

            async def import_sales_order(self, body, token_type, access_token):
                submitted.append((body, token_type, access_token))
                return {
                    "code": "2000",
                    "message": "导入处理完成.",
                    "success": True,
                    "total": 1,
                    "rows": [
                        {
                            "orderNumber": "10108260700027",
                            "headerId": "1091975",
                            "processStatusCode": "COMPLETE",
                        }
                    ],
                }

        class FailingEvents:
            async def emit(self, *_args, **_kwargs):
                raise RuntimeError("event sink unavailable")

        original_prepare = flow_module._prepare_erp_order
        original_client = flow_module.ErpSalesOrderClient
        flow_module._prepare_erp_order = prepare
        flow_module.ErpSalesOrderClient = FakeErpClient
        try:
            result = await flow_module.run(
                SimpleNamespace(
                    input={"po_no": "POJS2606030010"},
                    config=run_config(),
                    credentials=run_credentials(),
                    events=FailingEvents(),
                )
            )
        finally:
            flow_module._prepare_erp_order = original_prepare
            flow_module.ErpSalesOrderClient = original_client

        self.assertEqual(
            submitted,
            [(payload, "bearer", "mock-access-token")],
        )
        self.assertEqual(
            set(result),
            {
                "schemaVersion",
                "poNo",
                "orderNumber",
                "headerId",
                "supplierCode",
                "supplierName",
                "lineCount",
                "lines",
            },
        )
        self.assertEqual(
            result["schemaVersion"],
            "ORDER_DOWNLOAD_PUSH_OUTPUT_V1",
        )
        self.assertEqual(result["poNo"], "POJS2606030010")
        self.assertEqual(result["orderNumber"], "10108260700027")
        self.assertEqual(result["headerId"], "1091975")
        self.assertEqual(result["supplierCode"], "02556")
        self.assertEqual(
            result["supplierName"],
            "深圳市芯云信息科技有限公司",
        )
        self.assertEqual(result["lineCount"], 1)
        self.assertEqual(result["lines"], lines)
        self.assertTrue(
            {
                "draft",
                "draftOnly",
                "transmitted",
                "orderDetail",
                "erpPayload",
                "erpResponse",
                "credentials",
                "clientId",
                "clientSecret",
                "client_id",
                "client_secret",
                "accessToken",
                "access_token",
                "authorization",
                "password",
            }.isdisjoint(nested_keys(result))
        )

    async def test_run_emits_order_supplier_and_line_summary(self):
        payload = self.payload()
        lines = [
            {
                "lineNumber": "10",
                "customerItemNumber": "1B.30040.020227",
                "orderQuantity": "31200.0",
                "unitSellingPrice": "22.9448",
                "requestDate": "2026-06-24",
            },
            {
                "lineNumber": "20",
                "customerItemNumber": "1B.30040.020228",
                "orderQuantity": "100.0",
                "unitSellingPrice": "3.5",
                "requestDate": "2026-06-25",
            },
        ]

        async def prepare(_ctx):
            return {
                "draftOnly": True,
                "transmitted": False,
                "orderDetail": {
                    "supplierCode": "02556",
                    "supplierName": "深圳市芯云信息科技有限公司",
                    "lines": lines,
                },
                "erpPayload": payload,
            }

        class FakeErpClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def fetch_access_token(self):
                return "bearer", "mock-access-token"

            async def import_sales_order(self, *_args):
                return {
                    "code": "2000",
                    "message": "导入处理完成.",
                    "success": True,
                    "total": 1,
                    "rows": [
                        {
                            "orderNumber": "10108260700027",
                            "headerId": "1091975",
                            "processStatusCode": "COMPLETE",
                        }
                    ],
                }

        class RecordingEvents:
            def __init__(self):
                self.items = []

            async def emit(self, event_type, **kwargs):
                self.items.append({"type": event_type, **kwargs})

        events = RecordingEvents()
        original_prepare = flow_module._prepare_erp_order
        original_client = flow_module.ErpSalesOrderClient
        flow_module._prepare_erp_order = prepare
        flow_module.ErpSalesOrderClient = FakeErpClient
        try:
            result = await flow_module.run(
                SimpleNamespace(
                    input={"po_no": "POJS2606030010"},
                    config=run_config(),
                    credentials=run_credentials(),
                    events=events,
                )
            )
        finally:
            flow_module._prepare_erp_order = original_prepare
            flow_module.ErpSalesOrderClient = original_client

        succeeded = [
            item
            for item in events.items
            if item["type"] == "ERP_ORDER_IMPORT_SUCCEEDED"
        ]
        self.assertEqual(len(succeeded), 1)
        summary = succeeded[0]["payload"]
        self.assertEqual(summary["poNo"], "POJS2606030010")
        self.assertEqual(summary["orderNumber"], "10108260700027")
        self.assertEqual(summary["supplierCode"], "02556")
        self.assertEqual(
            summary["supplierName"],
            "深圳市芯云信息科技有限公司",
        )
        self.assertEqual(summary["lineCount"], 2)
        self.assertEqual(summary["lines"], lines)
        self.assertEqual(result["lines"], lines)

    async def test_run_maps_import_cancellation_to_human_required(self):
        payload = self.payload()

        async def prepare(_ctx):
            return {
                "draftOnly": True,
                "transmitted": False,
                "orderDetail": make_order_detail(),
                "erpPayload": payload,
            }

        class CancelledErpClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def fetch_access_token(self):
                return "bearer", "mock-access-token"

            async def import_sales_order(self, *_args):
                await asyncio.sleep(10)

        class RecordingEvents:
            async def emit(self, *_args, **_kwargs):
                return None

        original_prepare = flow_module._prepare_erp_order
        original_client = flow_module.ErpSalesOrderClient
        flow_module._prepare_erp_order = prepare
        flow_module.ErpSalesOrderClient = CancelledErpClient
        try:
            with self.assertRaises(RpaHumanRequiredError) as captured:
                await asyncio.wait_for(
                    flow_module.run(
                        SimpleNamespace(
                            input={"po_no": "POJS2606030010"},
                            config=run_config(),
                            credentials=run_credentials(),
                            events=RecordingEvents(),
                        )
                    ),
                    timeout=0.01,
                )
        finally:
            flow_module._prepare_erp_order = original_prepare
            flow_module.ErpSalesOrderClient = original_client

        self.assertEqual(
            captured.exception.code,
            "ERP_ORDER_IMPORT_OUTCOME_UNKNOWN",
        )

    async def test_run_attributes_token_failure_to_oauth_step(self):
        payload = self.payload()

        async def prepare(_ctx):
            return {
                "draftOnly": True,
                "transmitted": False,
                "orderDetail": make_order_detail(),
                "erpPayload": payload,
            }

        class FailingTokenClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def fetch_access_token(self):
                raise RpaFatalError("ERP_TOKEN_REJECTED", "token rejected")

        class RecordingEvents:
            def __init__(self):
                self.items = []

            async def emit(self, event_type, **kwargs):
                self.items.append({"type": event_type, **kwargs})

        events = RecordingEvents()
        original_prepare = flow_module._prepare_erp_order
        original_client = flow_module.ErpSalesOrderClient
        flow_module._prepare_erp_order = prepare
        flow_module.ErpSalesOrderClient = FailingTokenClient
        try:
            with self.assertRaises(RpaFatalError):
                await flow_module.run(
                    SimpleNamespace(
                        input={"po_no": "POJS2606030010"},
                        config=run_config(),
                        credentials=run_credentials(),
                        events=events,
                    )
                )
        finally:
            flow_module._prepare_erp_order = original_prepare
            flow_module.ErpSalesOrderClient = original_client

        failed = [item for item in events.items if item["type"] == "STEP_FAILED"]
        self.assertEqual(failed[-1]["payload"]["stepId"], "erp.oauth")

    async def test_run_emits_erp_row_failure_details(self):
        payload = self.payload()
        failed_row = {
            "orderNumber": None,
            "sourceHeaderId": None,
            "headerId": None,
            "soStatus": None,
            "soApprovedStatus": None,
            "processGroupId": "1784777664704",
            "processStatusCode": "ERROR",
            "processMessage": "客户料号与物料编码匹配失败",
        }

        async def prepare(_ctx):
            return {
                "draftOnly": True,
                "transmitted": False,
                "orderDetail": make_order_detail(),
                "erpPayload": payload,
            }

        class FailingRowClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def fetch_access_token(self):
                return "bearer", "mock-access-token"

            async def import_sales_order(self, *_args):
                raise RpaBusinessError(
                    "ERP_ORDER_IMPORT_ROW_FAILED",
                    failed_row["processMessage"],
                    details={"rows": [failed_row]},
                )

        class RecordingEvents:
            def __init__(self):
                self.items = []

            async def emit(self, event_type, **kwargs):
                self.items.append({"type": event_type, **kwargs})

        events = RecordingEvents()
        original_prepare = flow_module._prepare_erp_order
        original_client = flow_module.ErpSalesOrderClient
        flow_module._prepare_erp_order = prepare
        flow_module.ErpSalesOrderClient = FailingRowClient
        try:
            with self.assertRaises(RpaBusinessError) as captured:
                await flow_module.run(
                    SimpleNamespace(
                        input={"po_no": "POJS2606030010"},
                        config=run_config(),
                        credentials=run_credentials(),
                        events=events,
                    )
                )
        finally:
            flow_module._prepare_erp_order = original_prepare
            flow_module.ErpSalesOrderClient = original_client

        self.assertEqual(captured.exception.code, "ERP_ORDER_IMPORT_ROW_FAILED")
        failed = [item for item in events.items if item["type"] == "STEP_FAILED"]
        self.assertEqual(failed[-1]["payload"]["stepId"], "erp.import")
        self.assertEqual(failed[-1]["payload"]["rows"], [failed_row])

    async def test_run_rejects_placeholders_before_opening_portal(self):
        prepare_called = False

        async def prepare(_ctx):
            nonlocal prepare_called
            prepare_called = True

        original_prepare = flow_module._prepare_erp_order
        flow_module._prepare_erp_order = prepare
        try:
            with self.assertRaises(RpaFatalError) as captured:
                await flow_module.run(
                    SimpleNamespace(
                        config=run_config(),
                        credentials=run_credentials(erpClientId="__FILL_ERP_CLIENT_ID__"),
                    )
                )
        finally:
            flow_module._prepare_erp_order = original_prepare

        self.assertEqual(
            captured.exception.code,
            "ERP_CREDENTIALS_NOT_CONFIGURED",
        )
        self.assertFalse(prepare_called)

    async def test_run_rejects_missing_erp_base_before_opening_portal(self):
        prepare_called = False

        async def prepare(_ctx):
            nonlocal prepare_called
            prepare_called = True

        original_prepare = flow_module._prepare_erp_order
        flow_module._prepare_erp_order = prepare
        try:
            with self.assertRaises(RpaFatalError) as captured:
                await flow_module.run(
                    SimpleNamespace(
                        config=run_config(erpBaseUrl=""),
                        credentials=run_credentials(),
                    )
                )
        finally:
            flow_module._prepare_erp_order = original_prepare

        self.assertEqual(captured.exception.code, "ERP_ENDPOINT_NOT_CONFIGURED")
        self.assertFalse(prepare_called)


class OrderXlsxTests(unittest.TestCase):
    def test_extracts_every_attachment_business_field(self):
        result = parse_order_xlsx(make_xlsx())

        self.assertEqual(result["supplierCode"], "02556")
        self.assertEqual(result["supplierName"], "深圳市芯云信息科技有限公司")
        self.assertEqual(len(result["lines"]), 1)
        line = result["lines"][0]
        self.assertEqual(line["poNo"], "POJS2606030010")
        self.assertEqual(line["lineNumber"], "10")
        self.assertEqual(line["customerItemNumber"], "1B.30040.020227")
        self.assertEqual(line["orderQuantity"], "31200.0")
        self.assertEqual(line["unitSellingPrice"], "22.9448")
        self.assertEqual(line["requestDate"], "2026-06-24")
        self.assertEqual(line["directShipmentRemarks"], "是否中性:否;")

    def test_rejects_missing_required_attachment_column(self):
        headers = [item for item in HEADERS if item != "订单行号"]
        row = [value for index, value in enumerate(ROW) if HEADERS[index] != "订单行号"]

        with self.assertRaises(RpaBusinessError) as captured:
            parse_order_xlsx(make_xlsx(headers, [row]))

        self.assertEqual(captured.exception.code, "ORDER_ATTACHMENT_DATA_INCOMPLETE")

    def test_rejects_inconsistent_attachment_supplier(self):
        second = list(ROW)
        second[1] = "另一供应商"
        second[3] = "20"

        with self.assertRaises(RpaBusinessError) as captured:
            parse_order_xlsx(make_xlsx(rows=[ROW, second]))

        self.assertEqual(captured.exception.code, "ORDER_ATTACHMENT_DATA_INVALID")


class AttachmentReconciliationTests(unittest.TestCase):
    PO_NO = "POJS2607170001"
    PORTAL_LINES = [
        {"lineNumber": "10", "customerItemNumber": "1B.30040.020262"},
        {"lineNumber": "20", "customerItemNumber": "1B.30040.020257"},
        {"lineNumber": "30", "customerItemNumber": "1B.30040.020259"},
    ]

    def attachment(self, *, wrong_second_po=False):
        second_po = "POJS2607130002" if wrong_second_po else self.PO_NO
        return parse_order_xlsx(
            make_xlsx(
                rows=[
                    make_row(
                        "10",
                        "1B.30040.020262",
                        po_no=self.PO_NO,
                        quantity="100",
                        unit_price="1.13",
                        request_date="2026-08-10",
                        remarks="第一行备注",
                    ),
                    make_row(
                        "20",
                        "1B.30040.020257",
                        po_no=second_po,
                        quantity="200",
                        unit_price="2.26",
                        request_date="2026-08-11",
                        remarks="第二行备注",
                    ),
                    make_row(
                        "30",
                        "1B.30040.020259",
                        po_no=self.PO_NO,
                        quantity="300",
                        unit_price="3.39",
                        request_date="2026-08-12",
                        remarks="第三行备注",
                    ),
                ]
            )
        )

    def assert_error(self, code, portal_lines, attachment):
        with self.assertRaises(RpaBusinessError) as captured:
            reconcile_attachment_with_portal(
                self.PO_NO,
                portal_lines,
                attachment,
            )
        self.assertEqual(captured.exception.code, code)

    def test_clean_attachment_matches_without_po_normalization(self):
        attachment = self.attachment()

        normalized, reconciliation = reconcile_attachment_with_portal(
            self.PO_NO,
            self.PORTAL_LINES,
            attachment,
        )

        self.assertIsNot(normalized, attachment)
        self.assertEqual(reconciliation["portalLineCount"], 3)
        self.assertEqual(reconciliation["attachmentLineCount"], 3)
        self.assertEqual(reconciliation["normalizedPoNumberCount"], 0)
        self.assertEqual(
            [line["lineNumber"] for line in normalized["lines"]],
            ["10", "20", "30"],
        )
        self.assertTrue(all(line["poNo"] == self.PO_NO for line in normalized["lines"]))

    def test_regression_normalizes_only_wrong_po_field_before_erp(self):
        attachment = self.attachment(wrong_second_po=True)
        original_second = dict(attachment["lines"][1])

        normalized, reconciliation = reconcile_attachment_with_portal(
            self.PO_NO,
            self.PORTAL_LINES,
            attachment,
        )
        payload, resolved_lines = build_erp_draft(
            self.PO_NO,
            normalized,
            ordered_date="2026-07-31",
            customer_name=CUSTOMER_NAME,
            org_name=ORG_NAME,
        )

        self.assertEqual(reconciliation["normalizedPoNumberCount"], 1)
        self.assertEqual(
            [line["poNo"] for line in normalized["lines"]],
            [self.PO_NO, self.PO_NO, self.PO_NO],
        )
        self.assertEqual(
            [line["poNo"] for line in resolved_lines],
            [self.PO_NO, self.PO_NO, self.PO_NO],
        )
        self.assertEqual(
            [line["custPoNumber"] for line in payload[0]["lines"]],
            [self.PO_NO, self.PO_NO, self.PO_NO],
        )
        self.assertEqual(attachment["lines"][1], original_second)
        self.assertEqual(attachment["lines"][1]["poNo"], "POJS2607130002")
        for key, value in original_second.items():
            if key != "poNo":
                self.assertEqual(normalized["lines"][1][key], value, key)
        self.assertEqual(normalized["lines"][1]["orderQuantity"], "200")
        self.assertEqual(normalized["lines"][1]["unitSellingPrice"], "2.26")
        self.assertEqual(normalized["lines"][1]["requestDate"], "2026-08-11")
        self.assertEqual(normalized["lines"][1]["remarks"], "第二行备注")

    def test_output_order_follows_portal_detail_order(self):
        attachment = self.attachment()
        portal_lines = [
            self.PORTAL_LINES[2],
            self.PORTAL_LINES[0],
            self.PORTAL_LINES[1],
        ]

        normalized, _ = reconcile_attachment_with_portal(
            self.PO_NO,
            portal_lines,
            attachment,
        )

        self.assertEqual(
            [line["lineNumber"] for line in normalized["lines"]],
            ["30", "10", "20"],
        )

    def test_rejects_when_portal_is_missing_a_line(self):
        self.assert_error(
            "ORDER_ATTACHMENT_LINE_COUNT_MISMATCH",
            self.PORTAL_LINES[:2],
            self.attachment(),
        )

    def test_rejects_attachment_with_more_lines(self):
        attachment = self.attachment()
        attachment["lines"].append(
            parse_order_xlsx(
                make_xlsx(
                    rows=[
                        make_row(
                            "40",
                            "1B.30040.020280",
                            po_no=self.PO_NO,
                        )
                    ]
                )
            )["lines"][0]
        )
        self.assert_error(
            "ORDER_ATTACHMENT_LINE_COUNT_MISMATCH",
            self.PORTAL_LINES,
            attachment,
        )

    def test_rejects_attachment_with_fewer_lines(self):
        attachment = self.attachment()
        attachment["lines"] = attachment["lines"][:2]
        self.assert_error(
            "ORDER_ATTACHMENT_LINE_COUNT_MISMATCH",
            self.PORTAL_LINES,
            attachment,
        )

    def test_rejects_same_line_number_with_different_material(self):
        attachment = self.attachment()
        attachment["lines"][1]["customerItemNumber"] = "WRONG-MATERIAL"
        self.assert_error(
            "ORDER_ATTACHMENT_LINE_MISMATCH",
            self.PORTAL_LINES,
            attachment,
        )

    def test_allows_same_material_on_different_unique_line_numbers(self):
        portal_lines = [
            {"lineNumber": "10", "customerItemNumber": "SAME-MATERIAL"},
            {"lineNumber": "20", "customerItemNumber": "SAME-MATERIAL"},
        ]
        attachment = parse_order_xlsx(
            make_xlsx(
                rows=[
                    make_row("10", "SAME-MATERIAL", po_no=self.PO_NO),
                    make_row("20", "SAME-MATERIAL", po_no=self.PO_NO),
                ]
            )
        )

        normalized, reconciliation = reconcile_attachment_with_portal(
            self.PO_NO,
            portal_lines,
            attachment,
        )

        self.assertEqual(len(normalized["lines"]), 2)
        self.assertEqual(reconciliation["normalizedPoNumberCount"], 0)

    def test_rejects_duplicate_portal_line_number(self):
        portal_lines = [
            self.PORTAL_LINES[0],
            {"lineNumber": "10", "customerItemNumber": "OTHER-MATERIAL"},
            self.PORTAL_LINES[2],
        ]
        self.assert_error(
            "ORDER_DETAIL_LINE_DUPLICATE",
            portal_lines,
            self.attachment(),
        )

    def test_rejects_duplicate_attachment_line_number(self):
        attachment = self.attachment()
        attachment["lines"][1]["lineNumber"] = "10"
        self.assert_error(
            "ORDER_ATTACHMENT_LINE_DUPLICATE",
            self.PORTAL_LINES,
            attachment,
        )

    def test_rejects_unavailable_portal_lines(self):
        self.assert_error(
            "ORDER_DETAIL_LINES_UNAVAILABLE",
            [],
            self.attachment(),
        )

    def test_rejects_two_portal_lines_against_one_different_xlsx_line(self):
        portal_lines = self.PORTAL_LINES[:2]
        attachment = parse_order_xlsx(
            make_xlsx(
                rows=[
                    make_row(
                        "10",
                        "DIFFERENT-MATERIAL",
                        po_no="POJS2607130002",
                    )
                ]
            )
        )
        self.assert_error(
            "ORDER_ATTACHMENT_LINE_COUNT_MISMATCH",
            portal_lines,
            attachment,
        )


class ReconciliationPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconciliation_failure_prevents_erp_client_use(self):
        attachment = parse_order_xlsx(
            make_xlsx(
                rows=[
                    make_row(
                        "10",
                        "DIFFERENT-MATERIAL",
                        po_no="POJS2607130002",
                    )
                ]
            )
        )
        erp_client_calls = []

        class FakeAdapter:
            def __init__(self, _ctx):
                pass

            async def login(self):
                return None

            async def open_order_detail(self, _po_no):
                return None

            async def collect_order_line_identities(self):
                return [
                    {
                        "lineNumber": "10",
                        "customerItemNumber": "1B.30040.020262",
                    },
                    {
                        "lineNumber": "20",
                        "customerItemNumber": "1B.30040.020257",
                    },
                ]

            async def download_order(self):
                return attachment

        class ForbiddenErpClient:
            def __init__(self, **_kwargs):
                erp_client_calls.append("constructed")

        class RecordingLog:
            async def info(self, *_args):
                return None

        class ForbiddenArtifacts:
            async def screenshot(self, *_args, **_kwargs):
                self.fail("A reconciliation failure must not capture success evidence")

        events = RecordingEvents()
        original_adapter = flow_module.SupplierPortalAdapter
        original_client = flow_module.ErpSalesOrderClient
        flow_module.SupplierPortalAdapter = FakeAdapter
        flow_module.ErpSalesOrderClient = ForbiddenErpClient
        try:
            with self.assertRaises(RpaBusinessError) as captured:
                await flow_module.run(
                    SimpleNamespace(
                        portal_url="http://portal.test/",
                        input=MappingProxyType({"po_no": "POJS2607170001"}),
                        config=run_config(),
                        credentials=run_credentials(),
                        log=RecordingLog(),
                        artifacts=ForbiddenArtifacts(),
                        events=events,
                    )
                )
        finally:
            flow_module.SupplierPortalAdapter = original_adapter
            flow_module.ErpSalesOrderClient = original_client

        self.assertEqual(
            captured.exception.code,
            "ORDER_ATTACHMENT_LINE_COUNT_MISMATCH",
        )
        self.assertEqual(erp_client_calls, [])
        self.assertFalse(any(item["type"].startswith("ERP_") for item in events.items))

    async def test_regression_run_normalizes_erp_and_success_output(self):
        po_no = "POJS2607170001"
        portal_lines = [
            {"lineNumber": "10", "customerItemNumber": "1B.30040.020262"},
            {"lineNumber": "20", "customerItemNumber": "1B.30040.020257"},
            {"lineNumber": "30", "customerItemNumber": "1B.30040.020259"},
        ]
        attachment = parse_order_xlsx(
            make_xlsx(
                rows=[
                    make_row("10", "1B.30040.020262", po_no=po_no),
                    make_row(
                        "20",
                        "1B.30040.020257",
                        po_no="POJS2607130002",
                    ),
                    make_row("30", "1B.30040.020259", po_no=po_no),
                ]
            )
        )
        imported_payloads = []

        class FakeAdapter:
            def __init__(self, _ctx):
                pass

            async def login(self):
                return None

            async def open_order_detail(self, _po_no):
                return None

            async def collect_order_line_identities(self):
                return portal_lines

            async def download_order(self):
                return attachment

            async def wait_for_detail_stable(self):
                return None

        class FakeErpClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def fetch_access_token(self):
                return "bearer", "mock-access-token"

            async def import_sales_order(self, payload, *_args):
                imported_payloads.append(payload)
                return {
                    "code": "2000",
                    "message": "导入处理完成.",
                    "success": True,
                    "total": 1,
                    "rows": [
                        {
                            "orderNumber": "10108260700027",
                            "headerId": "1091975",
                            "processStatusCode": "COMPLETE",
                        }
                    ],
                }

        class RecordingLog:
            async def info(self, *_args):
                return None

        class RecordingArtifacts:
            async def screenshot(self, *_args, **_kwargs):
                return None

        events = RecordingEvents()
        original_adapter = flow_module.SupplierPortalAdapter
        original_client = flow_module.ErpSalesOrderClient
        flow_module.SupplierPortalAdapter = FakeAdapter
        flow_module.ErpSalesOrderClient = FakeErpClient
        try:
            result = await flow_module.run(
                SimpleNamespace(
                    portal_url="http://portal.test/",
                    input=MappingProxyType({"po_no": po_no}),
                    config=run_config(),
                    credentials=run_credentials(),
                    log=RecordingLog(),
                    artifacts=RecordingArtifacts(),
                    events=events,
                )
            )
        finally:
            flow_module.SupplierPortalAdapter = original_adapter
            flow_module.ErpSalesOrderClient = original_client

        self.assertEqual(result["schemaVersion"], "ORDER_DOWNLOAD_PUSH_OUTPUT_V1")
        self.assertEqual(result["poNo"], po_no)
        self.assertEqual(result["lineCount"], len(portal_lines))
        self.assertEqual(
            [line["poNo"] for line in result["lines"]],
            [po_no, po_no, po_no],
        )
        self.assertEqual(len(imported_payloads), 1)
        self.assertEqual(
            [line["custPoNumber"] for line in imported_payloads[0][0]["lines"]],
            [po_no, po_no, po_no],
        )
        reconciled = [
            item
            for item in events.items
            if item["type"] == "ORDER_ATTACHMENT_RECONCILED"
        ]
        self.assertEqual(len(reconciled), 1)
        self.assertEqual(
            reconciled[0]["payload"],
            {
                "poNo": po_no,
                "portalLineCount": 3,
                "attachmentLineCount": 3,
                "normalizedPoNumberCount": 1,
            },
        )


class ErpDraftTests(unittest.TestCase):
    def test_uses_only_xlsx_mapping_and_declared_defaults(self):
        attachment = parse_order_xlsx(make_xlsx())

        payload, resolved = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
            customer_name=CUSTOMER_NAME,
            org_name=ORG_NAME,
        )

        header = payload[0]
        line = header["lines"][0]
        self.assertEqual(header["orderNumber"], "")
        self.assertEqual(header["customerNumber"], "")
        self.assertEqual(header["customerName"], "天地偉業技術有限公司")
        self.assertEqual(header["orderType"], "常规订单")
        self.assertEqual(header["orderedDate"], "2026-07-22")
        self.assertEqual(header["currencyCode"], "")
        self.assertEqual(header["orgName"], "深圳市芯云信息科技有限公司")
        self.assertEqual(header["paymentTerm"], "")
        self.assertEqual(header["comments"], "")
        self.assertEqual(header["isAttachment"], "Y")
        for name in (
            "salesrep",
            "invoiceToLocation",
            "orgCode",
            "priceListName",
            "fobPointCode",
            "fob",
            "userNo",
            "sourceHeaderId",
        ):
            self.assertEqual(header[name], "", name)
        self.assertEqual(line["lineNumber"], "")
        self.assertEqual(line["lineType"], "")
        self.assertEqual(line["custPoLine"], "10")
        self.assertEqual(line["custPoNumber"], "POJS2606030010")
        self.assertEqual(line["custItemNum"], "1B.30040.020227")
        self.assertEqual(line["itemNumber"], "")
        self.assertEqual(line["itemDescription"], "")
        self.assertEqual(line["orderQuantity"], 31200)
        self.assertEqual(line["orderQuantityUom"], "")
        self.assertEqual(line["unitSellingPrice"], 22.9448)
        self.assertEqual(line["taxRate"], 0.13)
        self.assertEqual(line["unTaxPrice"], "20.3051")
        self.assertEqual(line["requestDate"], "2026-06-24")
        for name in (
            "priceListName",
            "factoryLocation",
            "customerJob",
            "productLine",
            "pm",
            "usdPrice",
            "deliveryRate",
            "actualExchangeRate",
            "sourceLineId",
        ):
            self.assertEqual(line[name], "", name)
        self.assertEqual(resolved[0]["taxRate"], "0.13")

    def test_does_not_map_direct_shipment_remarks_to_comments(self):
        attachment = parse_order_xlsx(make_xlsx())

        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
            customer_name=CUSTOMER_NAME,
            org_name=ORG_NAME,
        )

        self.assertEqual(
            attachment["lines"][0]["directShipmentRemarks"], "是否中性:否;"
        )
        self.assertEqual(payload[0]["comments"], "")

    def test_maps_distinct_xlsx_remarks_to_header_comments(self):
        first = list(ROW)
        first[18] = "请整单交付"
        second = list(ROW)
        second[3] = "20"
        second[18] = "防潮包装"
        attachment = parse_order_xlsx(make_xlsx(rows=[first, second]))

        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
            customer_name=CUSTOMER_NAME,
            org_name=ORG_NAME,
        )

        self.assertEqual(payload[0]["comments"], "请整单交付；防潮包装")

    def test_builds_erp_only_from_reconciled_purchase_order(self):
        row = list(ROW)
        row[2] = "PO-OTHER"
        attachment = parse_order_xlsx(make_xlsx(rows=[row]))
        normalized, _ = reconcile_attachment_with_portal(
            "POJS2606030010",
            [
                {
                    "lineNumber": "10",
                    "customerItemNumber": "1B.30040.020227",
                }
            ],
            attachment,
        )

        payload, resolved = build_erp_draft(
            "POJS2606030010",
            normalized,
            ordered_date="2026-07-22",
            customer_name=CUSTOMER_NAME,
            org_name=ORG_NAME,
        )

        self.assertEqual(
            payload[0]["lines"][0]["custPoNumber"],
            "POJS2606030010",
        )
        self.assertEqual(resolved[0]["poNo"], "POJS2606030010")
        self.assertEqual(attachment["lines"][0]["poNo"], "PO-OTHER")

    def test_normalizes_purchase_order_casing_before_erp(self):
        row = list(ROW)
        row[2] = "pojs2606030010"
        attachment = parse_order_xlsx(make_xlsx(rows=[row]))
        normalized, reconciliation = reconcile_attachment_with_portal(
            "POJS2606030010",
            [
                {
                    "lineNumber": "10",
                    "customerItemNumber": "1B.30040.020227",
                }
            ],
            attachment,
        )

        payload, _ = build_erp_draft(
            "POJS2606030010",
            normalized,
            ordered_date="2026-07-22",
            customer_name=CUSTOMER_NAME,
            org_name=ORG_NAME,
        )

        self.assertEqual(
            payload[0]["lines"][0]["custPoNumber"],
            "POJS2606030010",
        )
        self.assertEqual(reconciliation["normalizedPoNumberCount"], 1)

    def test_org_name_comes_from_portal_business_entity_not_xlsx(self):
        attachment = parse_order_xlsx(make_xlsx())
        other_org = "深圳市另一家信息科技有限公司"

        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
            customer_name=CUSTOMER_NAME,
            org_name=other_org,
        )

        self.assertEqual(attachment["supplierName"], ORG_NAME)
        self.assertEqual(payload[0]["orgName"], other_org)
        self.assertEqual(payload[0]["orgCode"], "")

    def test_reads_org_name_from_lease_business_entity(self):
        ctx = SimpleNamespace(config=run_config(), credentials=run_credentials())
        self.assertEqual(_org_name_from_ctx(ctx), ORG_NAME)

    def test_missing_business_entity_fails_before_erp(self):
        ctx = SimpleNamespace(
            config=run_config(businessEntity=""),
            credentials=run_credentials(),
        )
        with self.assertRaises(RpaBusinessError) as raised:
            _org_name_from_ctx(ctx)
        self.assertEqual(raised.exception.code, "ERP_REQUIRED_FIELD_MISSING")


if __name__ == "__main__":
    unittest.main()
