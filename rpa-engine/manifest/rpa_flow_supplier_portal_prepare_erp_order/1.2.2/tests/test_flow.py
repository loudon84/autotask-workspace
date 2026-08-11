import asyncio
import importlib.util
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
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
    "supplier_portal_prepare_erp_order_flow_1_2_1",
    FLOW_DIR / "flow.py",
)
if FLOW_SPEC is None or FLOW_SPEC.loader is None:
    raise RuntimeError("Flow module could not be loaded for tests")
flow_module = importlib.util.module_from_spec(FLOW_SPEC)
sys.modules[FLOW_SPEC.name] = flow_module
FLOW_SPEC.loader.exec_module(flow_module)

ERP_ORDER_IMPORT_URL = flow_module.ERP_ORDER_IMPORT_URL
ERP_TOKEN_URL = flow_module.ERP_TOKEN_URL
ErpSalesOrderClient = flow_module.ErpSalesOrderClient
_emit_erp_event_safely = flow_module._emit_erp_event_safely
build_erp_draft = flow_module.build_erp_draft
parse_order_xlsx = flow_module.parse_order_xlsx

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


class NavigationCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_an_authenticated_browser_session(self):
        timeline = []
        events = RecordingEvents()
        adapter = flow_module.SupplierPortalAdapter(
            SimpleNamespace(
                artifacts=SimpleNamespace(),
                credentials={"username": "portal-user", "password": "secret"},
                events=events,
                page=FakeNavigationPage(timeline, authenticated=True),
                portal_url="http://portal.test/",
                selectors={
                    "login_ready": "login-ready",
                    "login_success": "login-success",
                },
            )
        )

        await adapter.login()

        self.assertEqual(
            timeline,
            [
                ("goto", "http://portal.test/", "domcontentloaded"),
                ("wait", "login-ready", "visible", 10000),
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

        self.assertIn(
            (
                "wait",
                "ordinary-POJS2607130002, pending-POJS2607130002",
                "visible",
                15000,
            ),
            timeline,
        )
        self.assertEqual(events.items[-1]["type"], "STEP_SUCCEEDED")


class PackageContractTests(unittest.TestCase):
    def test_manifest_and_selectors_describe_1_2_2_test_compatibility(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        selectors = json.loads(
            (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["version"], "1.2.2")
        self.assertIn("portal-env-tag", selectors["login_ready"])
        self.assertIn("login-captcha-image", selectors["login_ready"])
        self.assertIn("order-detail-page", selectors["detail_page"])
        self.assertIn("pend-order-detail-page", selectors["detail_page"])
        self.assertIn("order-detail-no-{po_no}", selectors["detail_po_number"])
        self.assertIn(
            "pend-order-detail-no-{po_no}",
            selectors["detail_po_number"],
        )
        self.assertIn("order-detail-download-btn", selectors["download_order"])
        self.assertIn(
            "pend-order-detail-download-btn",
            selectors["download_order"],
        )
        self.assertIn(
            "pend-order-detail-lines-table",
            selectors["detail_rows"],
        )
        source = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertNotIn("ORDER_ATTACHMENT_PO_MISMATCH", source)


class DetailStabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_stable_detail_before_final_settle(self):
        timeline = []
        selectors = {
            "download_dialog": "dialog",
            "detail_page": "detail",
            "download_order": "download",
            "detail_rows": "rows",
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
                ("wait", "detail_rows", "visible", 10000),
                ("wait", "loading_mask", "hidden", 10000),
                ("assets", "detail"),
                (
                    "layout",
                    {"detailSelector": "detail", "rowSelector": "rows"},
                ),
                ("timeout", 150),
                (
                    "layout",
                    {"detailSelector": "detail", "rowSelector": "rows"},
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
            await flow_module._prepare_erp_order(
                SimpleNamespace(
                    portal_url="http://portal.test/",
                    input={"po_no": "POJS2606030010"},
                    log=RecordingLog(),
                    artifacts=RecordingArtifacts(),
                    events=RecordingEvents(),
                )
            )
        finally:
            flow_module.SupplierPortalAdapter = original_adapter

        self.assertLess(timeline.index("download"), timeline.index("stable"))
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
    def setUp(self):
        self.original_client_id = flow_module.ERP_CLIENT_ID
        self.original_client_secret = flow_module.ERP_CLIENT_SECRET
        flow_module.ERP_CLIENT_ID = "mock-client-id"
        flow_module.ERP_CLIENT_SECRET = "mock-client-secret"

    def tearDown(self):
        flow_module.ERP_CLIENT_ID = self.original_client_id
        flow_module.ERP_CLIENT_SECRET = self.original_client_secret

    def payload(self):
        attachment = parse_order_xlsx(make_xlsx())
        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
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
        async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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
        async with ErpSalesOrderClient(
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
        async with ErpSalesOrderClient(
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
                async with ErpSalesOrderClient(
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

    async def test_import_read_timeout_requires_human_verification(self):
        def handler(request):
            raise httpx.ReadTimeout("private timeout detail", request=request)

        async with ErpSalesOrderClient(
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
                async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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

        async with ErpSalesOrderClient(
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
                async with ErpSalesOrderClient(
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
        flow_module.ERP_CLIENT_ID = "__FILL_ERP_CLIENT_ID__"
        flow_module.ERP_CLIENT_SECRET = "__FILL_ERP_CLIENT_SECRET__"
        try:
            with self.assertRaises(RpaFatalError) as captured:
                await flow_module.run(SimpleNamespace())
        finally:
            flow_module._prepare_erp_order = original_prepare

        self.assertEqual(
            captured.exception.code,
            "ERP_CREDENTIALS_NOT_CONFIGURED",
        )
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


class ErpDraftTests(unittest.TestCase):
    def test_uses_only_xlsx_mapping_and_declared_defaults(self):
        attachment = parse_order_xlsx(make_xlsx())

        payload, resolved = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
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
        )

        self.assertEqual(payload[0]["comments"], "请整单交付；防潮包装")

    def test_accepts_attachment_for_another_purchase_order_during_test_stage(self):
        row = list(ROW)
        row[2] = "PO-OTHER"
        attachment = parse_order_xlsx(make_xlsx(rows=[row]))

        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
        )

        self.assertEqual(payload[0]["lines"][0]["custPoNumber"], "PO-OTHER")

    def test_preserves_xlsx_purchase_order_value_in_payload(self):
        row = list(ROW)
        row[2] = "pojs2606030010"
        attachment = parse_order_xlsx(make_xlsx(rows=[row]))

        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
        )

        self.assertEqual(
            payload[0]["lines"][0]["custPoNumber"],
            "pojs2606030010",
        )


if __name__ == "__main__":
    unittest.main()
