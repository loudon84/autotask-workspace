import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

import httpx

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaHumanRequiredError,
    RpaRetryableError,
)

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "supplier_portal_upload_order_attachment_flow_1_2_5",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

AttachmentSystemClient = flow_module.AttachmentSystemClient
validate_input = flow_module.validate_input

PO_NO = "POJS2607130002"
SOURCE_FILE_NAME = "PURCHASE_ORDER.pdf"
ATTACHMENT_NAME = PO_NO
ERP_TOKEN_URL = "http://erp.test/core/oauth/token"
ERP_UPLOAD_URL = "http://erp.test/core/api/srm/so/uploadAttachment"
UPLOAD_URL = "http://doc.test/upload"
ATTACHMENT_USERNAME = "SMC-SZ-HR15563"
CONTENT = b"%PDF-1.7\nmock-signed-contract"
FAKE_TOKEN = "unit-test-token"


def make_attachment_client(**kwargs):
    values = {
        "token_url": ERP_TOKEN_URL,
        "upload_url": ERP_UPLOAD_URL,
        "doc_upload_url": UPLOAD_URL,
        "client_id": "mock-client-id",
        "client_secret": "mock-client-secret",
    }
    values.update(kwargs)
    return AttachmentSystemClient(**values)


def response(request, status_code, payload=None, text=None):
    if text is not None:
        return httpx.Response(status_code, request=request, text=text)
    return httpx.Response(status_code, request=request, json=payload)


def token_response(request):
    return response(
        request,
        200,
        {"access_token": FAKE_TOKEN, "token_type": "bearer"},
    )


class RecordingEvents:
    def __init__(self, timeline):
        self.timeline = timeline

    async def emit(self, event_type, **kwargs):
        self.timeline.append(("event", event_type, kwargs))


class RecordingArtifacts:
    def __init__(self, timeline):
        self.timeline = timeline

    async def screenshot(self, name, *, step_id):
        self.timeline.append(("screenshot", name, step_id))


class RecordingLog:
    async def info(self, *_args, **_kwargs):
        return None


def make_ctx(timeline, input_value=None):
    return SimpleNamespace(
        input=(
            MappingProxyType({"po_no": PO_NO, "username": ATTACHMENT_USERNAME}) if input_value is None else input_value
        ),
        portal_url="http://portal.test/",
        credentials=MappingProxyType(
            {
                "username": "tester",
                "password": "not-a-real-password",
                "erpClientId": "mock-client-id",
                "erpClientSecret": "mock-client-secret",
            }
        ),
        config=MappingProxyType(
            {
                "erpBaseUrl": "http://erp.test",
                "docBaseUrl": "http://doc.test",
            }
        ),
        selectors={},
        events=RecordingEvents(timeline),
        artifacts=RecordingArtifacts(timeline),
        log=RecordingLog(),
        page=SimpleNamespace(),
    )


class FakeAdapter:
    instances = []

    def __init__(self, ctx):
        self.ctx = ctx
        self.timeline = ctx.events.timeline
        type(self).instances.append(self)

    async def login(self):
        self.timeline.append(("portal", "login"))

    async def open_order_detail(self, po_no):
        self.timeline.append(("portal", "open", po_no))

    async def wait_for_detail_stable(self, po_no):
        self.timeline.append(("portal", "stable", po_no))

    async def verify_signed(self):
        self.timeline.append(("portal", "verify_signed"))

    async def download_signed_contract(self):
        self.timeline.append(("portal", "download"))
        return {
            "sourceFileName": SOURCE_FILE_NAME,
            "size": len(CONTENT),
            "contentType": "application/pdf",
            "content": CONTENT,
        }


class FakeAttachmentClient:
    uploaded_record = None
    instances = []

    def __init__(self, **_kwargs):
        self.timeline = ACTIVE_TIMELINE
        self.upload_calls = []
        type(self).instances.append(self)

    async def __aenter__(self):
        self.timeline.append(("attachment", "open"))
        return self

    async def __aexit__(self, *_args):
        self.timeline.append(("attachment", "close"))

    async def upload(self, **kwargs):
        self.timeline.append(("attachment", "upload", kwargs["order_number"]))
        self.upload_calls.append(kwargs)
        return type(self).uploaded_record


ACTIVE_TIMELINE = []


class InputAndContractTests(unittest.TestCase):
    def test_accepts_engine_read_only_mapping(self):
        self.assertEqual(
            validate_input(
                MappingProxyType({"po_no": PO_NO, "username": ATTACHMENT_USERNAME})
            ),
            (PO_NO, ATTACHMENT_USERNAME),
        )

    def test_rejects_invalid_input(self):
        values = (
            None,
            {},
            {"po_no": ""},
            {"po_no": "../unsafe"},
            {"po_no": "PO WITH SPACE"},
            {"po_no": PO_NO},
            {"po_no": PO_NO, "username": ""},
            {"po_no": PO_NO, "username": "has space"},
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(RpaBusinessError) as captured:
                    validate_input(value)
                self.assertEqual(captured.exception.code, "FLOW_INPUT_INVALID")

    def test_manifest_and_selectors_define_frozen_contract(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        selectors = json.loads(
            (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            manifest["rpaFlowId"],
            "rpa_flow_supplier_portal_upload_order_attachment",
        )
        self.assertEqual(manifest["version"], "1.2.5")
        self.assertEqual(
            manifest["supportedWorkflowCodes"],
            ["srm_upload_order_attachment"],
        )
        self.assertIn("[data-rpa='order-detail-view-sign-btn']", selectors["view_sign"])
        source = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")
        self.assertIn("uploadAttachment", source)
        self.assertIn("SDMS_SO1", source)
        self.assertIn("custPoNumber", source)
        self.assertIn("core/oauth/token", source)
        self.assertIn("uploadUrl", source)
        self.assertIn("erpBaseUrl", source)
        self.assertIn("docBaseUrl", source)
        self.assertNotIn("192.168.99.111", source)
        self.assertNotIn("api.doc.uat.smart-core.com.hk", source)
        self.assertNotIn("SMC-SZ-HR15563", source)
        self.assertNotIn('ATTACHMENT_USERNAME = "S01"', source)


class AttachmentUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_uses_oauth_and_sdms_so_fields(self):
        requests = []

        async def handler(request):
            requests.append(request)
            if request.url.path.endswith("/oauth/token"):
                return token_response(request)
            return response(
                request,
                200,
                {"code": 2000, "success": True, "message": "ok"},
            )

        async with make_attachment_client(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await client.upload(
                order_number=PO_NO,
                username=ATTACHMENT_USERNAME,
                attachment_name=ATTACHMENT_NAME,
                source_file_name=SOURCE_FILE_NAME,
                content=CONTENT,
                content_type="application/octet-stream",
            )

        self.assertEqual(result["attachmentName"], ATTACHMENT_NAME)
        self.assertEqual(result["flag"], "SDMS_SO1")
        self.assertEqual(len(requests), 2)
        token_req, upload_req = requests
        self.assertEqual(token_req.method, "POST")
        self.assertTrue(token_req.url.path.endswith("/oauth/token"))
        self.assertEqual(token_req.url.params.get("grant_type"), "client_credentials")
        self.assertEqual(upload_req.method, "POST")
        self.assertEqual(
            upload_req.url.path,
            "/core/api/srm/so/uploadAttachment",
        )
        self.assertEqual(
            upload_req.headers.get("authorization"),
            f"bearer {FAKE_TOKEN}",
        )
        body = upload_req.content
        for value in (
            b'name="flag"',
            b"SDMS_SO1",
            b'name="custPoNumber"',
            PO_NO.encode(),
            b'name="username"',
            ATTACHMENT_USERNAME.encode(),
            b'name="filename"',
            ATTACHMENT_NAME.encode(),
            b'name="uploadUrl"',
            UPLOAD_URL.encode(),
            b'name="file"; filename="PURCHASE_ORDER.pdf"',
            CONTENT,
        ):
            self.assertIn(value, body)
        self.assertNotIn(b'name="order_number"', body)

    async def test_upload_accepts_legacy_code_200(self):
        async def handler(request):
            if request.url.path.endswith("/oauth/token"):
                return token_response(request)
            return response(request, 200, {"code": 200, "msg": "ok"})

        async with make_attachment_client(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await client.upload(
                order_number=PO_NO,
                username=ATTACHMENT_USERNAME,
                attachment_name=ATTACHMENT_NAME,
                source_file_name=SOURCE_FILE_NAME,
                content=CONTENT,
                content_type="application/octet-stream",
            )
        self.assertEqual(result["sourceFileName"], SOURCE_FILE_NAME)

    async def test_upload_http_503_is_outcome_unknown(self):
        async def handler(request):
            if request.url.path.endswith("/oauth/token"):
                return token_response(request)
            return response(request, 503, {"code": 503})

        async with make_attachment_client(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaHumanRequiredError) as captured:
                await client.upload(
                    order_number=PO_NO,
                    username=ATTACHMENT_USERNAME,
                    attachment_name=ATTACHMENT_NAME,
                    source_file_name=SOURCE_FILE_NAME,
                    content=CONTENT,
                    content_type="application/octet-stream",
                )

        self.assertEqual(
            captured.exception.code,
            "ATTACHMENT_UPLOAD_OUTCOME_UNKNOWN",
        )

    async def test_upload_explicit_rejection_is_business_failure(self):
        async def handler(request):
            if request.url.path.endswith("/oauth/token"):
                return token_response(request)
            return response(request, 422, {"code": 422})

        async with make_attachment_client(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaBusinessError) as captured:
                await client.upload(
                    order_number=PO_NO,
                    username=ATTACHMENT_USERNAME,
                    attachment_name=ATTACHMENT_NAME,
                    source_file_name=SOURCE_FILE_NAME,
                    content=CONTENT,
                    content_type="application/octet-stream",
                )

        self.assertEqual(captured.exception.code, "ATTACHMENT_UPLOAD_REJECTED")

    async def test_upload_surfaces_api_rejection_message(self):
        async def handler(request):
            if request.url.path.endswith("/oauth/token"):
                return token_response(request)
            return response(
                request,
                200,
                {
                    "code": 2001,
                    "success": False,
                    "message": "上传地址不能为空",
                },
            )

        async with make_attachment_client(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaBusinessError) as captured:
                await client.upload(
                    order_number=PO_NO,
                    username=ATTACHMENT_USERNAME,
                    attachment_name=ATTACHMENT_NAME,
                    source_file_name=SOURCE_FILE_NAME,
                    content=CONTENT,
                    content_type="application/octet-stream",
                )

        self.assertEqual(captured.exception.code, "ATTACHMENT_UPLOAD_REJECTED")
        self.assertIn("上传地址不能为空", captured.exception.safe_message)

    async def test_invalid_token_is_fatal(self):
        async def handler(request):
            if request.url.path.endswith("/oauth/token"):
                return token_response(request)
            return response(request, 401, {"error": "invalid_token"})

        async with make_attachment_client(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaFatalError) as captured:
                await client.upload(
                    order_number=PO_NO,
                    username=ATTACHMENT_USERNAME,
                    attachment_name=ATTACHMENT_NAME,
                    source_file_name=SOURCE_FILE_NAME,
                    content=CONTENT,
                    content_type="application/octet-stream",
                )

        self.assertEqual(captured.exception.code, "ERP_ACCESS_TOKEN_INVALID")

    async def test_token_service_unavailable_is_retryable(self):
        async def handler(request):
            return response(request, 503, {"error": "unavailable"})

        async with make_attachment_client(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaRetryableError) as captured:
                await client.upload(
                    order_number=PO_NO,
                    username=ATTACHMENT_USERNAME,
                    attachment_name=ATTACHMENT_NAME,
                    source_file_name=SOURCE_FILE_NAME,
                    content=CONTENT,
                    content_type="application/octet-stream",
                )

        self.assertEqual(captured.exception.code, "ERP_TOKEN_SERVICE_UNAVAILABLE")


class RunOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        global ACTIVE_TIMELINE
        ACTIVE_TIMELINE = []
        FakeAdapter.instances = []
        FakeAttachmentClient.instances = []
        FakeAttachmentClient.uploaded_record = {
            "attachmentId": "",
            "flag": "SDMS_SO1",
            "attachmentName": ATTACHMENT_NAME,
            "sourceFileName": SOURCE_FILE_NAME,
            "size": len(CONTENT),
            "uploader": ATTACHMENT_USERNAME,
        }

    async def run_flow(self):
        ctx = make_ctx(ACTIVE_TIMELINE)
        with (
            patch.object(
                flow_module,
                "SupplierPortalAttachmentAdapter",
                FakeAdapter,
            ),
            patch.object(
                flow_module,
                "AttachmentSystemClient",
                FakeAttachmentClient,
            ),
        ):
            result = await flow_module.run(ctx)
        return result, ctx

    async def test_downloads_then_uploads_without_legacy_query(self):
        result, _ctx = await self.run_flow()

        self.assertEqual(result["poNo"], PO_NO)
        self.assertEqual(result["custPoNumber"], PO_NO)
        self.assertTrue(result["uploaded"])
        self.assertFalse(result["idempotent"])
        relevant = [
            item
            for item in ACTIVE_TIMELINE
            if item[0] in {"portal", "screenshot", "attachment"}
        ]
        self.assertEqual(
            relevant,
            [
                ("portal", "login"),
                ("portal", "open", PO_NO),
                ("portal", "stable", PO_NO),
                ("portal", "verify_signed"),
                (
                    "screenshot",
                    "supplier-portal-signed-contract-before-download",
                    "file.download",
                ),
                ("portal", "download"),
                ("attachment", "open"),
                ("attachment", "upload", PO_NO),
                ("attachment", "close"),
            ],
        )
        client = FakeAttachmentClient.instances[0]
        self.assertEqual(len(client.upload_calls), 1)
        self.assertEqual(client.upload_calls[0]["order_number"], PO_NO)
        self.assertEqual(client.upload_calls[0]["username"], ATTACHMENT_USERNAME)
        self.assertEqual(client.upload_calls[0]["content"], CONTENT)
        self.assertEqual(
            client.upload_calls[0]["attachment_name"],
            f"{PO_NO}{Path(SOURCE_FILE_NAME).suffix}",
        )

    async def test_requires_signed_before_contract_download(self):
        class UnsignedAdapter(FakeAdapter):
            async def verify_signed(self):
                self.timeline.append(("portal", "verify_signed"))
                raise RpaBusinessError(
                    "ORDER_NOT_SIGNED",
                    "订单尚未已回签（当前：待签章），不能下载双方签章合同",
                )

        ctx = make_ctx(ACTIVE_TIMELINE)
        with (
            patch.object(
                flow_module,
                "SupplierPortalAttachmentAdapter",
                UnsignedAdapter,
            ),
            patch.object(
                flow_module,
                "AttachmentSystemClient",
                FakeAttachmentClient,
            ),
        ):
            with self.assertRaises(RpaBusinessError) as captured:
                await flow_module.run(ctx)

        self.assertEqual(captured.exception.code, "ORDER_NOT_SIGNED")
        self.assertNotIn(("portal", "download"), ACTIVE_TIMELINE)
        self.assertEqual(FakeAttachmentClient.instances, [])


if __name__ == "__main__":
    unittest.main()
