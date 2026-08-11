import asyncio
import mimetypes
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote

import httpx

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaFatalError,
    RpaHumanRequiredError,
    RpaRetryableError,
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
PO_NUMBER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
ATTACHMENT_API_BASE_URL = "http://api.doc.uat.smart-core.com.hk"
ATTACHMENT_FLAG = "sdms"
ATTACHMENT_USERNAME = "S01"
ATTACHMENT_NAME_PREFIX = "采购订单"
OUTPUT_SCHEMA_VERSION = "ORDER_ATTACHMENT_UPLOAD_OUTPUT_V1"
MAX_ATTACHMENT_BYTES = 200 * 1024 * 1024
QUERY_TIMEOUT_SECONDS = 15
UPLOAD_TIMEOUT_SECONDS = 60
VERIFY_ATTEMPTS = 5
VERIFY_INTERVAL_SECONDS = 1


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def validate_input(raw_input):
    value = raw_input if isinstance(raw_input, Mapping) else {}
    po_no = _clean(value.get("po_no")).upper()
    if not PO_NUMBER_PATTERN.fullmatch(po_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Customer purchase order number is missing or invalid",
        )
    return po_no


def resolve_captcha_code(image_src):
    if not isinstance(image_src, str) or not image_src.strip():
        return None
    clean_src = image_src.split("?", 1)[0].split("#", 1)[0]
    filename = clean_src.replace("\\", "/").rsplit("/", 1)[-1]
    return CAPTCHA_CODES.get(filename.rsplit(".", 1)[0].casefold())


def _response_object(response):
    try:
        value = response.json()
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, Mapping) else None


def _success_code(value):
    return _clean(value) == "200"


def _positive_size(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _safe_attachment_record(raw):
    if not isinstance(raw, Mapping):
        return None
    attachment_id = raw.get("id")
    if isinstance(attachment_id, bool) or attachment_id is None:
        return None
    attachment_id = _clean(attachment_id)
    size = _positive_size(raw.get("size"))
    record = {
        "attachmentId": attachment_id,
        "flag": _clean(raw.get("flag")),
        "attachmentName": _clean(raw.get("name")),
        "sourceFileName": _clean(raw.get("name_src")),
        "size": size,
        "uploader": _clean(raw.get("username")),
        "uploadedAt": _clean(raw.get("time")),
        "sizeFormat": _clean(raw.get("size_format")),
    }
    if (
        not record["attachmentId"]
        or not record["flag"]
        or not record["attachmentName"]
        or not record["sourceFileName"]
        or record["size"] is None
        or not record["uploader"]
        or not record["uploadedAt"]
        or not _clean(raw.get("path"))
    ):
        return None
    return record


def _file_identity(attachment_name, source_file_name, size):
    return {
        "flag": ATTACHMENT_FLAG,
        "attachmentName": attachment_name,
        "sourceFileName": source_file_name,
        "size": size,
    }


def _is_exact_match(record, expected):
    return (
        record["flag"].casefold() == expected["flag"].casefold()
        and record["attachmentName"] == expected["attachmentName"]
        and record["sourceFileName"] == expected["sourceFileName"]
        and record["size"] == expected["size"]
    )


def _is_name_conflict(record, expected):
    same_display_name = record["attachmentName"] == expected["attachmentName"]
    same_source_name = record["sourceFileName"] == expected["sourceFileName"]
    return (same_display_name or same_source_name) and not _is_exact_match(
        record,
        expected,
    )


def _matching_record(records, expected, *, attachment_id=None):
    matches = [record for record in records if _is_exact_match(record, expected)]
    if attachment_id is not None:
        expected_id = _clean(attachment_id)
        return next(
            (
                record
                for record in matches
                if record["attachmentId"] == expected_id
            ),
            None,
        )
    return matches[0] if matches else None


def _success_result(po_no, record, *, uploaded, idempotent):
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "poNo": po_no,
        "attachmentOrderNumber": po_no,
        "attachmentId": record["attachmentId"],
        "attachmentName": record["attachmentName"],
        "sourceFileName": record["sourceFileName"],
        "size": record["size"],
        "uploader": record["uploader"],
        "uploaded": uploaded,
        "idempotent": idempotent,
    }


async def _safe_emit(ctx, event_type, *, level="INFO", message, payload=None):
    try:
        await ctx.events.emit(
            event_type,
            level=level,
            message=message,
            payload=payload,
        )
    except Exception:
        return


async def _safe_failure_screenshot(ctx, name, step_id):
    try:
        await ctx.artifacts.screenshot(name, step_id=step_id)
    except Exception:
        return

class AttachmentSystemClient:
    def __init__(self, *, transport=None, verify_interval=None):
        self.transport = transport
        self.verify_interval = (
            VERIFY_INTERVAL_SECONDS if verify_interval is None else verify_interval
        )
        self.client = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=ATTACHMENT_API_BASE_URL,
            follow_redirects=False,
            transport=self.transport,
            trust_env=False,
        )
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback
        if self.client is not None:
            try:
                await self.client.aclose()
            except Exception:
                pass
            self.client = None

    def _active_client(self):
        if self.client is None:
            raise RpaFatalError(
                "ATTACHMENT_HTTP_CLIENT_UNAVAILABLE",
                "Attachment system HTTP client is unavailable",
            )
        return self.client

    async def query(self, order_number):
        path = "/order/{}/{}".format(
            quote(ATTACHMENT_FLAG, safe=""),
            quote(order_number, safe=""),
        )
        try:
            response = await self._active_client().get(
                path,
                headers={"Accept": "application/json"},
                timeout=QUERY_TIMEOUT_SECONDS,
            )
        except httpx.RequestError:
            raise RpaRetryableError(
                "ATTACHMENT_QUERY_FAILED",
                "Attachment query endpoint could not be reached",
            ) from None

        if 300 <= response.status_code < 400:
            raise RpaFatalError(
                "ATTACHMENT_QUERY_REDIRECT_REJECTED",
                "Attachment query endpoint returned an unsupported redirect",
            )
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise RpaRetryableError(
                "ATTACHMENT_QUERY_FAILED",
                "Attachment query endpoint is temporarily unavailable",
            )
        if not 200 <= response.status_code < 300:
            raise RpaBusinessError(
                "ATTACHMENT_QUERY_REJECTED",
                "Attachment system rejected the order attachment query",
            )

        value = _response_object(response)
        if value is None or not _success_code(value.get("code")):
            raise RpaFatalError(
                "ATTACHMENT_QUERY_RESPONSE_INVALID",
                "Attachment query endpoint returned an invalid response",
            )
        raw_records = value.get("data")
        if not isinstance(raw_records, list):
            raise RpaFatalError(
                "ATTACHMENT_QUERY_RESPONSE_INVALID",
                "Attachment query data must be an array",
            )
        records = [_safe_attachment_record(raw) for raw in raw_records]
        if any(record is None for record in records):
            raise RpaFatalError(
                "ATTACHMENT_QUERY_RESPONSE_INVALID",
                "Attachment query returned an invalid attachment record",
            )
        return records

    async def upload(
        self,
        *,
        order_number,
        attachment_name,
        source_file_name,
        content,
        content_type,
    ):
        try:
            response = await self._active_client().post(
                "/upload",
                headers={"Accept": "application/json"},
                data={
                    "flag": ATTACHMENT_FLAG,
                    "order_number": order_number,
                    "username": ATTACHMENT_USERNAME,
                    "filename": attachment_name,
                },
                files={
                    "file": (
                        source_file_name,
                        content,
                        content_type,
                    )
                },
                timeout=UPLOAD_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError:
            raise RpaHumanRequiredError(
                "ATTACHMENT_UPLOAD_OUTCOME_UNKNOWN",
                "Attachment upload requires manual verification",
            ) from None
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.PoolTimeout,
        ):
            raise RpaRetryableError(
                "ATTACHMENT_UPLOAD_CONNECTION_FAILED",
                "Attachment upload endpoint could not be reached",
            ) from None
        except httpx.RequestError:
            raise RpaHumanRequiredError(
                "ATTACHMENT_UPLOAD_OUTCOME_UNKNOWN",
                "Attachment upload requires manual verification",
            ) from None

        if 300 <= response.status_code < 400:
            raise RpaFatalError(
                "ATTACHMENT_UPLOAD_REDIRECT_REJECTED",
                "Attachment upload endpoint returned an unsupported redirect",
            )
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise RpaHumanRequiredError(
                "ATTACHMENT_UPLOAD_OUTCOME_UNKNOWN",
                "Attachment upload requires manual verification",
            )
        if not 200 <= response.status_code < 300:
            raise RpaBusinessError(
                "ATTACHMENT_UPLOAD_REJECTED",
                "Attachment system rejected the order attachment upload",
            )

        value = _response_object(response)
        if value is None:
            raise RpaHumanRequiredError(
                "ATTACHMENT_UPLOAD_RESPONSE_INVALID",
                "Attachment upload response requires manual verification",
            )
        if not _success_code(value.get("code")):
            raise RpaBusinessError(
                "ATTACHMENT_UPLOAD_REJECTED",
                "Attachment system rejected the order attachment upload",
            )
        record = _safe_attachment_record(value.get("data"))
        if record is None:
            raise RpaHumanRequiredError(
                "ATTACHMENT_UPLOAD_RESPONSE_INVALID",
                "Attachment upload response requires manual verification",
            )
        expected = _file_identity(
            attachment_name,
            source_file_name,
            len(content),
        )
        if (
            not _is_exact_match(record, expected)
            or record["uploader"] != ATTACHMENT_USERNAME
        ):
            raise RpaHumanRequiredError(
                "ATTACHMENT_UPLOAD_RESPONSE_INVALID",
                "Attachment upload response does not match the submitted file",
            )
        return record

    async def verify_upload(self, order_number, expected, attachment_id):
        for attempt in range(VERIFY_ATTEMPTS):
            try:
                records = await self.query(order_number)
            except (
                RpaBusinessError,
                RpaFatalError,
                RpaRetryableError,
            ) as exc:
                raise RpaHumanRequiredError(
                    "ATTACHMENT_UPLOAD_VERIFICATION_UNCONFIRMED",
                    "Uploaded attachment could not be verified",
                ) from exc
            record = _matching_record(
                records,
                expected,
                attachment_id=attachment_id,
            )
            if record is not None:
                return record
            if any(_is_name_conflict(item, expected) for item in records):
                raise RpaHumanRequiredError(
                    "ATTACHMENT_UPLOAD_VERIFICATION_UNCONFIRMED",
                    "Attachment query returned a conflicting uploaded file",
                )
            if attempt + 1 < VERIFY_ATTEMPTS:
                await asyncio.sleep(self.verify_interval)
        raise RpaHumanRequiredError(
            "ATTACHMENT_UPLOAD_VERIFICATION_UNCONFIRMED",
            "Uploaded attachment was not visible in the query endpoint",
        )
class SupplierPortalAttachmentAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = ctx.page
        self.selectors = ctx.selectors

    def selector(self, name, po_no=None):
        value = self.selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError(
                "FLOW_SELECTOR_MISSING",
                f"Required supplier portal selector is missing: {name}",
            )
        return value.replace("{po_no}", po_no) if po_no else value

    async def login(self):
        step_id = "srm.login"
        username = _clean(self.ctx.credentials.get("username"))
        password = str(self.ctx.credentials.get("password", ""))
        if not username or not password:
            raise RpaFatalError(
                "SRM_CREDENTIALS_MISSING",
                "Supplier portal credentials are unavailable",
            )
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Logging in to supplier portal",
            payload={"stepId": step_id, "stepType": step_id},
        )
        await self.page.goto(self.ctx.portal_url, wait_until="domcontentloaded")
        try:
            await self.page.locator(self.selector("login_ready")).wait_for(
                state="visible",
                timeout=10000,
            )
        except Exception as exc:
            raise RpaRetryableError(
                "SRM_LOGIN_TIMEOUT",
                "Supplier portal login page did not become ready",
            ) from exc
        if await self.page.locator(self.selector("login_success")).is_visible():
            await self.ctx.events.emit(
                "STEP_SUCCEEDED",
                message="Supplier portal authenticated session reused",
                payload={"stepId": step_id, "reusedSession": True},
            )
            return
        captcha = self.page.locator(self.selector("captcha_image"))
        code = resolve_captcha_code(await captcha.get_attribute("src"))
        if code is None:
            await self._redact_login_fields()
            await self.ctx.artifacts.screenshot(
                "supplier-portal-captcha-unknown",
                step_id=step_id,
            )
            raise RpaHumanRequiredError(
                "HUMAN_VERIFICATION_REQUIRED",
                "Supplier portal CAPTCHA requires human verification",
            )
        try:
            await self.page.fill(self.selector("username"), username)
            await self.page.fill(self.selector("password"), password)
            await self.page.fill(self.selector("captcha"), code)
            agreement = self.page.locator(self.selector("agreement"))
            if not await agreement.is_checked():
                await agreement.check()
            await self.page.click(self.selector("login_button"))
            await self._wait_for_login_result()
        except (RpaBusinessError, RpaRetryableError):
            raise
        except Exception as exc:
            await self._redact_login_fields()
            raise RpaRetryableError(
                "SRM_LOGIN_FAILED",
                "Supplier portal login failed",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Supplier portal login completed",
            payload={"stepId": step_id},
        )

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

    async def open_order_detail(self, po_no):
        step_id = "srm.search_po"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Opening customer purchase order detail",
            payload={"stepId": step_id, "stepType": step_id},
        )
        portal_root = self.ctx.portal_url.split("#", 1)[0].rstrip("/")
        await self.page.goto(
            f"{portal_root}/#/supplier/orders",
            wait_until="domcontentloaded",
        )
        await self.page.locator(self.selector("order_page")).wait_for(
            state="visible",
            timeout=10000,
        )
        await self.page.fill(self.selector("po_number"), po_no)
        await self.page.click(self.selector("search_button"))
        row = self.page.locator(self.selector("order_row", po_no))
        try:
            await row.wait_for(state="visible", timeout=10000)
        except Exception as exc:
            raise RpaBusinessError(
                "BUSINESS_NOT_FOUND",
                "Customer purchase order was not found",
            ) from exc
        await self.page.click(self.selector("order_detail", po_no))
        try:
            await self.page.locator(
                self.selector("detail_po_number", po_no)
            ).wait_for(state="visible", timeout=15000)
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DETAIL_UNAVAILABLE",
                "Customer purchase order detail could not be verified",
            ) from exc
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Customer purchase order detail opened",
            payload={"stepId": step_id, "poNo": po_no},
        )

    async def wait_for_detail_stable(self, po_no):
        try:
            await self.page.locator(self.selector("detail_page")).wait_for(
                state="visible",
                timeout=10000,
            )
            await self.page.locator(
                self.selector("detail_po_number", po_no)
            ).wait_for(state="visible", timeout=10000)
            await self.page.locator(self.selector("download_order")).wait_for(
                state="visible",
                timeout=10000,
            )
            await self.page.locator(self.selector("detail_rows")).first.wait_for(
                state="visible",
                timeout=10000,
            )
            await self.page.locator(self.selector("loading_mask")).wait_for(
                state="hidden",
                timeout=10000,
            )
            await self.page.evaluate(
                """
                async (detailSelector) => {
                  const detail = document.querySelector(detailSelector);
                  if (!detail) throw new Error('order detail is unavailable');
                  const visible = (node) => {
                    const rect = node.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                  };
                  const images = [...detail.querySelectorAll('img')].filter(visible);
                  await Promise.all([
                    document.fonts?.ready ?? Promise.resolve(),
                    ...images.map((image) => image.complete
                      ? Promise.resolve()
                      : new Promise((resolve, reject) => {
                          image.addEventListener('load', resolve, {once: true});
                          image.addEventListener('error', reject, {once: true});
                        })),
                  ]);
                  const snapshot = () => {
                    const rect = detail.getBoundingClientRect();
                    return JSON.stringify({
                      x: rect.x,
                      y: rect.y,
                      width: rect.width,
                      height: rect.height,
                      scrollWidth: detail.scrollWidth,
                      scrollHeight: detail.scrollHeight,
                    });
                  };
                  let previous = snapshot();
                  for (let attempt = 0; attempt < 10; attempt += 1) {
                    await new Promise((resolve) => requestAnimationFrame(
                      () => requestAnimationFrame(resolve),
                    ));
                    const current = snapshot();
                    if (current === previous) return;
                    previous = current;
                  }
                  throw new Error('order detail layout did not stabilize');
                }
                """,
                self.selector("detail_page"),
            )
            await self.page.wait_for_timeout(300)
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_DETAIL_UNSTABLE",
                "Customer purchase order detail did not become stable",
            ) from exc
    async def download_order(self):
        step_id = "file.download"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Downloading customer purchase order attachment",
            payload={"stepId": step_id, "stepType": step_id},
        )
        try:
            await self.page.click(self.selector("download_order"))
            confirm = self.page.locator(self.selector("download_confirm"))
            await confirm.wait_for(state="visible", timeout=5000)
            async with self.page.expect_download(timeout=15000) as info:
                await confirm.click()
            download = await info.value
            suggested = _clean(getattr(download, "suggested_filename", ""))
            safe_name = Path(suggested).name
            if (
                not suggested
                or suggested != safe_name
                or len(safe_name) > 240
                or any(ord(char) < 32 for char in safe_name)
            ):
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_NAME_INVALID",
                    "Supplier portal returned an invalid attachment filename",
                )
            raw_path = await download.path()
            if not raw_path:
                raise RpaRetryableError(
                    "ORDER_ATTACHMENT_DOWNLOAD_FAILED",
                    "Downloaded order attachment path is unavailable",
                )
            content = await asyncio.to_thread(Path(raw_path).read_bytes)
            if not content:
                raise RpaRetryableError(
                    "ORDER_ATTACHMENT_EMPTY",
                    "Supplier portal returned an empty order attachment",
                )
            if len(content) > MAX_ATTACHMENT_BYTES:
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_TOO_LARGE",
                    "Supplier portal order attachment exceeds the size limit",
                )
            artifact = await self.ctx.artifacts.save_download(
                download,
                safe_name,
                step_id=step_id,
            )
            if getattr(artifact, "size", None) != len(content):
                raise RpaRetryableError(
                    "ORDER_ATTACHMENT_ARTIFACT_INVALID",
                    "Order attachment Artifact size could not be verified",
                )
            try:
                await self.page.locator(self.selector("download_dialog")).wait_for(
                    state="hidden",
                    timeout=10000,
                )
            except Exception:
                pass
        except (RpaBusinessError, RpaRetryableError):
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_ATTACHMENT_DOWNLOAD_FAILED",
                "Customer purchase order attachment could not be downloaded",
            ) from exc
        content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Customer purchase order attachment downloaded",
            payload={
                "stepId": step_id,
                "sourceFileName": safe_name,
                "size": len(content),
            },
        )
        return {
            "sourceFileName": safe_name,
            "size": len(content),
            "contentType": content_type,
            "content": content,
        }


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError(
            "PORTAL_URL_MISSING",
            "Supplier portal URL is unavailable",
        )
    po_no = validate_input(getattr(ctx, "input", None))
    await ctx.log.info(
        "Starting order attachment upload Flow",
        {"poNo": po_no},
    )

    adapter = SupplierPortalAttachmentAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)
    await adapter.wait_for_detail_stable(po_no)
    await ctx.artifacts.screenshot(
        "supplier-portal-order-attachment-before-download",
        step_id="file.download",
    )
    attachment = await adapter.download_order()

    attachment_name = f"{ATTACHMENT_NAME_PREFIX}{po_no}"
    expected = _file_identity(
        attachment_name,
        attachment["sourceFileName"],
        attachment["size"],
    )

    async with AttachmentSystemClient() as client:
        await ctx.events.emit(
            "STEP_STARTED",
            message="Checking existing order attachments",
            payload={
                "stepId": "attachment.query.preflight",
                "stepType": "attachment.query",
                "poNo": po_no,
            },
        )
        records = await client.query(po_no)
        existing = _matching_record(records, expected)
        if existing is not None:
            await _safe_emit(
                ctx,
                "STEP_SUCCEEDED",
                message="Matching order attachment already exists",
                payload={
                    "stepId": "attachment.query.preflight",
                    "poNo": po_no,
                    "attachmentId": existing["attachmentId"],
                    "idempotent": True,
                },
            )
            return _success_result(
                po_no,
                existing,
                uploaded=False,
                idempotent=True,
            )
        if any(_is_name_conflict(record, expected) for record in records):
            error = RpaHumanRequiredError(
                "ATTACHMENT_DUPLICATE_CONFLICT",
                "An existing attachment has the same name but different file data",
            )
            await _safe_failure_screenshot(
                ctx,
                "attachment-system-duplicate-conflict",
                "attachment.query.preflight",
            )
            await _safe_emit(
                ctx,
                "STEP_WAITING_HUMAN",
                level="WARNING",
                message="Existing order attachment conflicts with downloaded file",
                payload={
                    "stepId": "attachment.query.preflight",
                    "errorCode": error.code,
                    "poNo": po_no,
                },
            )
            raise error
        await _safe_emit(
            ctx,
            "STEP_SUCCEEDED",
            message="No matching order attachment exists",
            payload={
                "stepId": "attachment.query.preflight",
                "poNo": po_no,
                "existingAttachmentCount": len(records),
            },
        )

        await _safe_emit(
            ctx,
            "STEP_STARTED",
            message="Uploading order attachment",
            payload={
                "stepId": "attachment.upload",
                "stepType": "attachment.upload",
                "poNo": po_no,
                "sourceFileName": attachment["sourceFileName"],
                "size": attachment["size"],
            },
        )
        try:
            uploaded = await client.upload(
                order_number=po_no,
                attachment_name=attachment_name,
                source_file_name=attachment["sourceFileName"],
                content=attachment["content"],
                content_type=attachment["contentType"],
            )
            verified = await client.verify_upload(
                po_no,
                expected,
                uploaded["attachmentId"],
            )
        except RpaHumanRequiredError as error:
            await _safe_failure_screenshot(
                ctx,
                "attachment-system-upload-outcome-unknown",
                "attachment.upload",
            )
            await _safe_emit(
                ctx,
                "STEP_WAITING_HUMAN",
                level="WARNING",
                message="Order attachment upload requires manual verification",
                payload={
                    "stepId": "attachment.upload",
                    "errorCode": error.code,
                    "poNo": po_no,
                },
            )
            raise

    await _safe_emit(
        ctx,
        "STEP_SUCCEEDED",
        message="Order attachment uploaded and verified",
        payload={
            "stepId": "attachment.upload",
            "poNo": po_no,
            "attachmentId": verified["attachmentId"],
            "sourceFileName": verified["sourceFileName"],
            "size": verified["size"],
        },
    )
    return _success_result(
        po_no,
        verified,
        uploaded=True,
        idempotent=False,
    )