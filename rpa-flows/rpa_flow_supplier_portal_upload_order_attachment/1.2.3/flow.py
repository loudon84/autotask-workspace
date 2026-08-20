import asyncio
import mimetypes
import re
from collections.abc import Mapping
from pathlib import Path

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
ERP_TOKEN_PATH = "/core/oauth/token"
ERP_UPLOAD_ATTACHMENT_PATH = "/core/api/srm/so/uploadAttachment"
DOC_UPLOAD_PATH = "/upload"
ERP_CLIENT_ID_PLACEHOLDER = "__FILL_ERP_CLIENT_ID__"
ERP_CLIENT_SECRET_PLACEHOLDER = "__FILL_ERP_CLIENT_SECRET__"
ERP_TOKEN_TIMEOUT_SECONDS = 15.0
ATTACHMENT_FLAG = "SDMS_SO1"
OUTPUT_SCHEMA_VERSION = "ORDER_ATTACHMENT_UPLOAD_OUTPUT_V1"
_HTTP_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
SIGNED_REPLY_STATUS = "已回签"
PDF_MAGIC = b"%PDF"
MAX_ATTACHMENT_BYTES = 200 * 1024 * 1024
UPLOAD_TIMEOUT_SECONDS = 60


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _ctx_text(ctx, *keys):
    sources = (_mapping(getattr(ctx, "config", None)), _mapping(getattr(ctx, "credentials", None)))
    for key in keys:
        for source in sources:
            text = str(source.get(key) or "").strip()
            if text:
                return text
    return ""


def _join_url(base, path):
    return f"{str(base).strip().rstrip('/')}/{str(path).lstrip('/')}"


def _require_erp_base(ctx):
    base = _ctx_text(ctx, "erpBaseUrl")
    if not base:
        raise RpaFatalError(
            "ERP_ENDPOINT_NOT_CONFIGURED",
            "ERP base URL is not configured",
        )
    return base


def _require_doc_base(ctx):
    base = _ctx_text(ctx, "docBaseUrl")
    if not base:
        raise RpaFatalError(
            "ERP_ENDPOINT_NOT_CONFIGURED",
            "Document upload base URL is not configured",
        )
    return base


def validate_input(raw_input):
    value = raw_input if isinstance(raw_input, Mapping) else {}
    po_no = _clean(value.get("po_no")).upper()
    if not PO_NUMBER_PATTERN.fullmatch(po_no):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Customer purchase order number is missing or invalid",
        )
    username = _clean(value.get("username"))
    if (
        not username
        or len(username) > 64
        or any(ord(char) < 32 for char in username)
        or " " in username
    ):
        raise RpaBusinessError(
            "FLOW_INPUT_INVALID",
            "Auth login username is missing or invalid",
        )
    return po_no, username


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


def _erp_credentials(client_id, client_secret):
    resolved_client_id = str(client_id or "").strip()
    resolved_client_secret = str(client_secret or "")
    if (
        not resolved_client_id
        or not resolved_client_secret.strip()
        or resolved_client_id == ERP_CLIENT_ID_PLACEHOLDER
        or resolved_client_secret == ERP_CLIENT_SECRET_PLACEHOLDER
    ):
        raise RpaFatalError(
            "ERP_CREDENTIALS_NOT_CONFIGURED",
            "ERP OAuth client credentials are not configured",
        )
    return resolved_client_id, resolved_client_secret


def _upload_succeeded(payload):
    if not isinstance(payload, Mapping):
        return False
    if _clean(payload.get("error")).casefold() == "invalid_token":
        return False
    if payload.get("success") is False:
        return False
    if payload.get("success") is True:
        return True
    return _clean(payload.get("code")) in {"200", "2000", "1"}


def _public_api_text(value, *, limit=400):
    text = _clean(value)
    if not text:
        return ""
    text = _HTTP_URL_PATTERN.sub("<url>", text)
    return text[:limit]


def _row_failure_notes(payload):
    rows = payload.get("rows") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return []
    notes = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("success") is True:
            continue
        so_no = _clean(row.get("orderNumber") or row.get("order_number"))
        reason = _public_api_text(
            row.get("message") or row.get("processMessage") or row.get("msg"),
            limit=120,
        )
        if so_no and reason:
            notes.append(f"{so_no}: {reason}")
        elif reason:
            notes.append(reason)
        if len(notes) >= 3:
            break
    return notes


def _rejection_message(payload):
    default = "Attachment system rejected the order attachment upload"
    if not isinstance(payload, Mapping):
        return default
    message = _public_api_text(payload.get("message") or payload.get("msg"))
    extras = _row_failure_notes(payload)
    if message and extras:
        return f"{message}（{'；'.join(extras)}）"[:400]
    return message or (extras[0] if extras else default)


def _local_upload_record(attachment_name, source_file_name, size, username):
    return {
        "attachmentId": "",
        "flag": ATTACHMENT_FLAG,
        "attachmentName": attachment_name,
        "sourceFileName": source_file_name,
        "size": size,
        "uploader": username,
    }


def _success_result(po_no, record, *, uploaded, idempotent):
    return {
        "schemaVersion": OUTPUT_SCHEMA_VERSION,
        "poNo": po_no,
        "attachmentOrderNumber": po_no,
        "custPoNumber": po_no,
        "attachmentId": record.get("attachmentId") or "",
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
    def __init__(
        self,
        *,
        token_url,
        upload_url,
        doc_upload_url,
        client_id,
        client_secret,
        transport=None,
    ):
        self.token_url = token_url
        self.upload_url = upload_url
        self.doc_upload_url = doc_upload_url
        self.transport = transport
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = None
        self._token_type = None
        self._access_token = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
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
        self._token_type = None
        self._access_token = None

    def _active_client(self):
        if self.client is None:
            raise RpaFatalError(
                "ATTACHMENT_HTTP_CLIENT_UNAVAILABLE",
                "Attachment system HTTP client is unavailable",
            )
        return self.client

    async def fetch_access_token(self):
        client_id, client_secret = _erp_credentials(
            self.client_id,
            self.client_secret,
        )
        try:
            response = await self._active_client().post(
                self.token_url,
                params={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
                timeout=ERP_TOKEN_TIMEOUT_SECONDS,
            )
        except httpx.RequestError:
            raise RpaRetryableError(
                "ERP_TOKEN_REQUEST_FAILED",
                "ERP access token could not be requested",
            ) from None

        if 300 <= response.status_code < 400:
            raise RpaFatalError(
                "ERP_TOKEN_REDIRECT_REJECTED",
                "ERP token endpoint returned an unsupported redirect",
            )
        if response.status_code == 429 or response.status_code >= 500:
            raise RpaRetryableError(
                "ERP_TOKEN_SERVICE_UNAVAILABLE",
                "ERP token service is temporarily unavailable",
            )
        if not 200 <= response.status_code < 300:
            raise RpaFatalError(
                "ERP_TOKEN_REJECTED",
                "ERP token service rejected the configured client",
            )

        value = _response_object(response)
        if value is None:
            raise RpaFatalError(
                "ERP_TOKEN_RESPONSE_INVALID",
                "ERP token service returned an invalid response",
            )
        raw_access_token = value.get("access_token")
        raw_token_type = value.get("token_type")
        access_token = (
            raw_access_token.strip() if isinstance(raw_access_token, str) else ""
        )
        token_type = (
            raw_token_type.strip().casefold() if isinstance(raw_token_type, str) else ""
        )
        if not access_token or token_type != "bearer":
            raise RpaFatalError(
                "ERP_TOKEN_RESPONSE_INVALID",
                "ERP token service returned an invalid response",
            )
        self._token_type = token_type
        self._access_token = access_token
        return token_type, access_token

    async def _ensure_token(self):
        if self._token_type and self._access_token:
            return self._token_type, self._access_token
        return await self.fetch_access_token()

    async def upload(
        self,
        *,
        order_number,
        username,
        attachment_name,
        source_file_name,
        content,
        content_type,
    ):
        token_type, access_token = await self._ensure_token()
        try:
            response = await self._active_client().post(
                self.upload_url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"{token_type} {access_token}",
                },
                data={
                    "flag": ATTACHMENT_FLAG,
                    "custPoNumber": order_number,
                    "username": username,
                    "filename": attachment_name,
                    "uploadUrl": self.doc_upload_url,
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

        value = _response_object(response)
        if (
            isinstance(value, Mapping)
            and _clean(value.get("error")).casefold() == "invalid_token"
        ):
            raise RpaFatalError(
                "ERP_ACCESS_TOKEN_INVALID",
                "ERP access token was rejected",
            )
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
                _rejection_message(value),
            )
        if value is None:
            raise RpaHumanRequiredError(
                "ATTACHMENT_UPLOAD_RESPONSE_INVALID",
                "Attachment upload response requires manual verification",
            )
        if not _upload_succeeded(value):
            raise RpaBusinessError(
                "ATTACHMENT_UPLOAD_REJECTED",
                _rejection_message(value),
            )
        return _local_upload_record(
            attachment_name,
            source_file_name,
            len(content),
            username,
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
            await self.page.locator(self.selector("view_sign")).wait_for(
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
    async def reply_status(self):
        tags = self.page.locator(self.selector("reply_status"))
        count = await tags.count()
        for index in range(count):
            text = _clean(await tags.nth(index).inner_text())
            if text in {SIGNED_REPLY_STATUS, "待回签", "待签章"}:
                return text
        if count:
            return _clean(await tags.first.inner_text())
        return ""

    async def verify_signed(self):
        status = await self.reply_status()
        if status != SIGNED_REPLY_STATUS:
            raise RpaBusinessError(
                "ORDER_NOT_SIGNED",
                f"订单尚未已回签（当前：{status or '未知'}），不能下载双方签章合同",
            )
        view_sign = self.page.locator(self.selector("view_sign"))
        if await view_sign.count() == 0:
            raise RpaBusinessError(
                "SIGNED_CONTRACT_BUTTON_MISSING",
                "已回签订单缺少「查看签章」入口，无法下载双方签章合同",
            )

    async def download_signed_contract(self):
        step_id = "file.download"
        await self.ctx.events.emit(
            "STEP_STARTED",
            message="Downloading bilaterally signed contract",
            payload={"stepId": step_id, "stepType": step_id},
        )
        try:
            # 已回签详情：「查看签章」直接触发合同 PDF 下载（不是「下载订单」的 XLSX/XML）
            async with self.page.expect_download(timeout=20000) as info:
                await self.page.click(self.selector("view_sign"))
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
                    "门户返回的签章合同文件名无效",
                )
            raw_path = await download.path()
            if not raw_path:
                raise RpaRetryableError(
                    "ORDER_ATTACHMENT_DOWNLOAD_FAILED",
                    "签章合同本地下载路径不可用",
                )
            content = await asyncio.to_thread(Path(raw_path).read_bytes)
            if not content:
                raise RpaRetryableError(
                    "ORDER_ATTACHMENT_EMPTY",
                    "门户返回的签章合同为空",
                )
            if not content.startswith(PDF_MAGIC):
                # 正式环境也可能是 PDF 以外的合同格式；至少拒绝明显订单表（xlsx/zip xml）
                lower = safe_name.casefold()
                if lower.endswith((".xlsx", ".xls", ".xml", ".csv")) or content[:2] == b"PK":
                    raise RpaBusinessError(
                        "SIGNED_CONTRACT_WRONG_FILE",
                        "下载到的是订单文件而非双方签章合同，请检查门户「查看签章」入口",
                    )
            if len(content) > MAX_ATTACHMENT_BYTES:
                raise RpaBusinessError(
                    "ORDER_ATTACHMENT_TOO_LARGE",
                    "签章合同超过大小限制",
                )
            artifact = await self.ctx.artifacts.save_download(
                download,
                safe_name,
                step_id=step_id,
            )
            if getattr(artifact, "size", None) != len(content):
                raise RpaRetryableError(
                    "ORDER_ATTACHMENT_ARTIFACT_INVALID",
                    "签章合同 Artifact 大小校验失败",
                )
        except (RpaBusinessError, RpaRetryableError):
            raise
        except Exception as exc:
            raise RpaRetryableError(
                "ORDER_ATTACHMENT_DOWNLOAD_FAILED",
                "双方签章合同下载失败",
            ) from exc
        content_type = mimetypes.guess_type(safe_name)[0] or "application/pdf"
        await self.ctx.events.emit(
            "STEP_SUCCEEDED",
            message="Bilaterally signed contract downloaded",
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

    async def download_order(self):
        # 兼容旧测试替身：正式路径请用 download_signed_contract
        return await self.download_signed_contract()


async def run(ctx):
    if not getattr(ctx, "portal_url", None):
        raise RpaFatalError(
            "PORTAL_URL_MISSING",
            "Supplier portal URL is unavailable",
        )
    po_no, username = validate_input(getattr(ctx, "input", None))
    client_id, client_secret = _erp_credentials(
        _ctx_text(ctx, "erpClientId"),
        _ctx_text(ctx, "erpClientSecret"),
    )
    erp_base = _require_erp_base(ctx)
    doc_base = _require_doc_base(ctx)
    await ctx.log.info(
        "Starting signed contract attachment upload Flow",
        {"poNo": po_no},
    )

    adapter = SupplierPortalAttachmentAdapter(ctx)
    await adapter.login()
    await adapter.open_order_detail(po_no)
    await adapter.wait_for_detail_stable(po_no)
    await adapter.verify_signed()
    await ctx.artifacts.screenshot(
        "supplier-portal-signed-contract-before-download",
        step_id="file.download",
    )
    attachment = await adapter.download_signed_contract()

    attachment_name = po_no

    async with AttachmentSystemClient(
        token_url=_join_url(erp_base, ERP_TOKEN_PATH),
        upload_url=_join_url(erp_base, ERP_UPLOAD_ATTACHMENT_PATH),
        doc_upload_url=_join_url(doc_base, DOC_UPLOAD_PATH),
        client_id=client_id,
        client_secret=client_secret,
    ) as client:
        await _safe_emit(
            ctx,
            "STEP_STARTED",
            message="Uploading signed contract to SDMS",
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
                username=username,
                attachment_name=attachment_name,
                source_file_name=attachment["sourceFileName"],
                content=attachment["content"],
                content_type=attachment["contentType"],
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
        message="Order attachment uploaded to SDMS",
        payload={
            "stepId": "attachment.upload",
            "poNo": po_no,
            "custPoNumber": po_no,
            "sourceFileName": uploaded["sourceFileName"],
            "size": uploaded["size"],
        },
    )
    return _success_result(
        po_no,
        uploaded,
        uploaded=True,
        idempotent=False,
    )