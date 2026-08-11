import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaHumanRequiredError,
    RpaRetryableError,
)

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "supplier_portal_upload_order_attachment_flow",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

AttachmentSystemClient = flow_module.AttachmentSystemClient
validate_input = flow_module.validate_input

PO_NO = "POJS2607130002"
SOURCE_FILE_NAME = "order.xlsx"
ATTACHMENT_NAME = f"采购订单{PO_NO}"
CONTENT = b"mock-order-file"
CONTENT_SIZE = len(CONTENT)


def raw_record(
    *,
    attachment_id=1,
    name=ATTACHMENT_NAME,
    source_file_name=SOURCE_FILE_NAME,
    size=CONTENT_SIZE,
    username="S01",
):
    return {
        "id": attachment_id,
        "flag": "sdms",
        "name": name,
        "name_src": source_file_name,
        "path": "opaque-storage-path",
        "size": size,
        "username": username,
        "time": "2026-07-30 09:28:38",
        "size_format": f"{size} B",
    }


def safe_record(**kwargs):
    return flow_module._safe_attachment_record(raw_record(**kwargs))


def response(request, status_code, payload=None, text=None):
    if text is not None:
        return httpx.Response(status_code, request=request, text=text)
    return httpx.Response(status_code, request=request, json=payload)


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
            MappingProxyType({"po_no": PO_NO}) if input_value is None else input_value
        ),
        portal_url="http://portal.test/",
        credentials=MappingProxyType(
            {"username": "tester", "password": "not-a-real-password"}
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

    async def verify_signed(self, po_no):
        self.timeline.append(("portal", "verify_signed", po_no))

    async def wait_for_detail_stable(self, po_no):
        self.timeline.append(("portal", "stable", po_no))

    async def download_order(self):
        self.timeline.append(("portal", "download"))
        return {
            "sourceFileName": SOURCE_FILE_NAME,
            "size": len(CONTENT),
            "contentType": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            "content": CONTENT,
        }


class FakeAttachmentClient:
    query_records = []
    uploaded_record = None
    verified_record = None
    instances = []

    def __init__(self):
        self.timeline = ACTIVE_TIMELINE
        self.upload_calls = []
        type(self).instances.append(self)

    async def __aenter__(self):
        self.timeline.append(("attachment", "open"))
        return self

    async def __aexit__(self, *_args):
        self.timeline.append(("attachment", "close"))

    async def query(self, order_number):
        self.timeline.append(("attachment", "query", order_number))
        return list(type(self).query_records)

    async def upload(self, **kwargs):
        self.timeline.append(("attachment", "upload", kwargs["order_number"]))
        self.upload_calls.append(kwargs)
        return type(self).uploaded_record

    async def verify_upload(self, order_number, expected, attachment_id):
        del expected
        self.timeline.append(("attachment", "verify", order_number, attachment_id))
        return type(self).verified_record


ACTIVE_TIMELINE = []


class InputAndContractTests(unittest.TestCase):
    def test_accepts_engine_read_only_mapping(self):
        self.assertEqual(
            validate_input(MappingProxyType({"po_no": PO_NO})),
            PO_NO,
        )

    def test_rejects_invalid_input(self):
        values = (
            None,
            {},
            {"po_no": ""},
            {"po_no": "../unsafe"},
            {"po_no": "PO WITH SPACE"},
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
        self.assertEqual(manifest["version"], "1.0.0")
        self.assertEqual(
            manifest["supportedWorkflowCodes"],
            ["srm_upload_order_attachment"],
        )
        self.assertEqual(
            manifest["inputSchema"],
            [
                {
                    "name": "po_no",
                    "type": "string",
                    "required": True,
                    "description": "Signed customer purchase order number",
                }
            ],
        )
        self.assertIn("[data-rpa='order-detail-page']", selectors["detail_page"])
        self.assertIn(
            "[data-rpa='pend-order-detail-page']",
            selectors["detail_page"],
        )
        self.assertIn(
            "[data-rpa='order-detail-download-btn']",
            selectors["download_order"],
        )

    def test_safe_record_never_exposes_storage_path(self):
        record = safe_record()

        self.assertIsNotNone(record)
        self.assertNotIn("path", record)
        self.assertEqual(record["attachmentId"], "1")
        self.assertEqual(record["size"], len(CONTENT))

    def test_invalid_external_record_is_rejected(self):
        invalid = raw_record()
        invalid["path"] = ""

        self.assertIsNone(flow_module._safe_attachment_record(invalid))

    def test_exact_match_requires_flag_names_and_size(self):
        expected = flow_module._file_identity(
            ATTACHMENT_NAME,
            SOURCE_FILE_NAME,
            len(CONTENT),
        )

        self.assertTrue(flow_module._is_exact_match(safe_record(), expected))
        self.assertFalse(
            flow_module._is_exact_match(
                safe_record(size=len(CONTENT) + 1),
                expected,
            )
        )


class AttachmentQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_accepts_numeric_and_string_success_code(self):
        for code in (200, "200"):
            with self.subTest(code=code):

                async def handler(request, code=code):
                    self.assertEqual(
                        request.url.path,
                        f"/order/sdms/{PO_NO}",
                    )
                    return response(
                        request,
                        200,
                        {"code": code, "msg": "success", "data": [raw_record()]},
                    )

                async with AttachmentSystemClient(
                    transport=httpx.MockTransport(handler)
                ) as client:
                    records = await client.query(PO_NO)

                self.assertEqual(records, [safe_record()])

    async def test_query_accepts_empty_data(self):
        async def handler(request):
            return response(
                request,
                200,
                {"code": 200, "msg": "success", "data": []},
            )

        async with AttachmentSystemClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            records = await client.query(PO_NO)

        self.assertEqual(records, [])

    async def test_query_maps_temporary_http_failure_to_retryable(self):
        async def handler(request):
            return response(request, 503, {"code": 503})

        async with AttachmentSystemClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaRetryableError) as captured:
                await client.query(PO_NO)

        self.assertEqual(captured.exception.code, "ATTACHMENT_QUERY_FAILED")

    async def test_query_rejects_malformed_response(self):
        responses = (
            {"code": 200, "data": {}},
            {"code": 500, "data": []},
            {"code": 200, "data": [{"id": 1}]},
        )
        for payload in responses:
            with self.subTest(payload=payload):

                async def handler(request, payload=payload):
                    return response(request, 200, payload)

                async with AttachmentSystemClient(
                    transport=httpx.MockTransport(handler)
                ) as client:
                    with self.assertRaises(RpaFatalError) as captured:
                        await client.query(PO_NO)
                self.assertEqual(
                    captured.exception.code,
                    "ATTACHMENT_QUERY_RESPONSE_INVALID",
                )


class AttachmentUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_posts_documented_multipart_fields_once(self):
        requests = []

        async def handler(request):
            requests.append(request)
            return response(
                request,
                200,
                {"code": 200, "msg": "上传成功", "data": raw_record()},
            )

        async with AttachmentSystemClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await client.upload(
                order_number=PO_NO,
                attachment_name=ATTACHMENT_NAME,
                source_file_name=SOURCE_FILE_NAME,
                content=CONTENT,
                content_type="application/octet-stream",
            )

        self.assertEqual(result, safe_record())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].method, "POST")
        self.assertEqual(requests[0].url.path, "/upload")
        self.assertNotIn("authorization", requests[0].headers)
        body = requests[0].content
        for value in (
            b'name="flag"',
            b"sdms",
            b'name="order_number"',
            PO_NO.encode(),
            b'name="username"',
            b"S01",
            b'name="filename"',
            ATTACHMENT_NAME.encode(),
            b'name="file"; filename="order.xlsx"',
            CONTENT,
        ):
            self.assertIn(value, body)

    async def test_upload_http_503_is_outcome_unknown(self):
        async def handler(request):
            return response(request, 503, {"code": 503})

        async with AttachmentSystemClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaHumanRequiredError) as captured:
                await client.upload(
                    order_number=PO_NO,
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
            return response(request, 422, {"code": 422})

        async with AttachmentSystemClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaBusinessError) as captured:
                await client.upload(
                    order_number=PO_NO,
                    attachment_name=ATTACHMENT_NAME,
                    source_file_name=SOURCE_FILE_NAME,
                    content=CONTENT,
                    content_type="application/octet-stream",
                )

        self.assertEqual(captured.exception.code, "ATTACHMENT_UPLOAD_REJECTED")

    async def test_upload_response_identity_mismatch_requires_human(self):
        async def handler(request):
            return response(
                request,
                200,
                {
                    "code": 200,
                    "data": raw_record(size=len(CONTENT) + 1),
                },
            )

        async with AttachmentSystemClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RpaHumanRequiredError) as captured:
                await client.upload(
                    order_number=PO_NO,
                    attachment_name=ATTACHMENT_NAME,
                    source_file_name=SOURCE_FILE_NAME,
                    content=CONTENT,
                    content_type="application/octet-stream",
                )

        self.assertEqual(
            captured.exception.code,
            "ATTACHMENT_UPLOAD_RESPONSE_INVALID",
        )

    async def test_verify_upload_retries_query_without_reposting(self):
        expected = flow_module._file_identity(
            ATTACHMENT_NAME,
            SOURCE_FILE_NAME,
            len(CONTENT),
        )
        client = AttachmentSystemClient(verify_interval=0)
        client.query = AsyncMock(side_effect=[[], [safe_record()]])

        result = await client.verify_upload(PO_NO, expected, "1")

        self.assertEqual(result, safe_record())
        self.assertEqual(client.query.await_count, 2)

    async def test_verify_query_failure_requires_human(self):
        expected = flow_module._file_identity(
            ATTACHMENT_NAME,
            SOURCE_FILE_NAME,
            len(CONTENT),
        )
        client = AttachmentSystemClient(verify_interval=0)
        client.query = AsyncMock(
            side_effect=RpaRetryableError("QUERY_FAILED", "query failed")
        )

        with self.assertRaises(RpaHumanRequiredError) as captured:
            await client.verify_upload(PO_NO, expected, "1")

        self.assertEqual(
            captured.exception.code,
            "ATTACHMENT_UPLOAD_VERIFICATION_UNCONFIRMED",
        )


class RunOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        global ACTIVE_TIMELINE
        ACTIVE_TIMELINE = []
        FakeAdapter.instances = []
        FakeAttachmentClient.instances = []
        FakeAttachmentClient.query_records = []
        FakeAttachmentClient.uploaded_record = safe_record()
        FakeAttachmentClient.verified_record = safe_record()

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

    async def test_new_file_downloads_then_queries_uploads_and_verifies(self):
        result, _ctx = await self.run_flow()

        self.assertEqual(
            result,
            {
                "schemaVersion": "ORDER_ATTACHMENT_UPLOAD_OUTPUT_V1",
                "poNo": PO_NO,
                "attachmentOrderNumber": PO_NO,
                "attachmentId": "1",
                "attachmentName": ATTACHMENT_NAME,
                "sourceFileName": SOURCE_FILE_NAME,
                "size": len(CONTENT),
                "uploader": "S01",
                "uploaded": True,
                "idempotent": False,
            },
        )
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
                ("portal", "verify_signed", PO_NO),
                ("portal", "stable", PO_NO),
                (
                    "screenshot",
                    "supplier-portal-order-attachment-before-download",
                    "file.download",
                ),
                ("portal", "download"),
                ("attachment", "open"),
                ("attachment", "query", PO_NO),
                ("attachment", "upload", PO_NO),
                ("attachment", "verify", PO_NO, "1"),
                ("attachment", "close"),
            ],
        )
        client = FakeAttachmentClient.instances[0]
        self.assertEqual(len(client.upload_calls), 1)
        self.assertEqual(client.upload_calls[0]["order_number"], PO_NO)
        self.assertEqual(
            client.upload_calls[0]["attachment_name"],
            ATTACHMENT_NAME,
        )
        self.assertEqual(client.upload_calls[0]["content"], CONTENT)

    async def test_exact_existing_file_is_idempotent_and_never_posts(self):
        FakeAttachmentClient.query_records = [safe_record()]

        result, _ctx = await self.run_flow()

        self.assertFalse(result["uploaded"])
        self.assertTrue(result["idempotent"])
        client = FakeAttachmentClient.instances[0]
        self.assertEqual(client.upload_calls, [])
        self.assertNotIn(
            ("attachment", "upload", PO_NO),
            ACTIVE_TIMELINE,
        )

    async def test_unrelated_attachment_does_not_block_upload(self):
        FakeAttachmentClient.query_records = [
            safe_record(
                attachment_id=99,
                name="其他附件",
                source_file_name="other.pdf",
                size=10,
            )
        ]

        result, _ctx = await self.run_flow()

        self.assertTrue(result["uploaded"])
        self.assertEqual(
            len(FakeAttachmentClient.instances[0].upload_calls),
            1,
        )

    async def test_same_name_with_different_size_requires_human(self):
        FakeAttachmentClient.query_records = [
            safe_record(attachment_id=9, size=len(CONTENT) + 1)
        ]

        with self.assertRaises(RpaHumanRequiredError) as captured:
            await self.run_flow()

        self.assertEqual(
            captured.exception.code,
            "ATTACHMENT_DUPLICATE_CONFLICT",
        )
        self.assertEqual(
            FakeAttachmentClient.instances[0].upload_calls,
            [],
        )
        self.assertIn(
            (
                "screenshot",
                "attachment-system-duplicate-conflict",
                "attachment.query.preflight",
            ),
            ACTIVE_TIMELINE,
        )

    async def test_not_signed_stops_before_download_and_upload(self):
        class NotSignedAdapter(FakeAdapter):
            async def verify_signed(self, po_no):
                raise RpaBusinessError(
                    "ORDER_NOT_SIGNED",
                    "Customer purchase order is not signed",
                    details={"poNo": po_no},
                )

        ctx = make_ctx(ACTIVE_TIMELINE)
        with (
            patch.object(
                flow_module,
                "SupplierPortalAttachmentAdapter",
                NotSignedAdapter,
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
