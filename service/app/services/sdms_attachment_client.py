"""把发票文件挂到 SDMS 对账单（HTTP 附件服务，非 RPA）。"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

UPLOAD_TIMEOUT_SECONDS = 60
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
# SDMS 对账单发票附件接口固定业务字段，环境无关。
STATEMENT_ATTACHMENT_FLAG = "SDMS_ARR"
_SUCCESS_CODES = {"200", "1", 200, 1}


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _is_success_code(value: object) -> bool:
    if value in _SUCCESS_CODES:
        return True
    return _clean(value) in {"200", "1"}


async def upload_statement_invoices_to_sdms(
    *,
    check_num: str,
    username: str,
    file_paths: list[str],
    db: "AsyncSession | None" = None,
    task_id: str | None = None,
    tenant_id: str | None = None,
    run_id: str | None = None,
) -> str | None:
    """逐个上传。全部成功返回 None；否则返回可展示给客服的原因。不抛业务异常。

    传入 db/task_id/tenant_id 时，每个文件 POST 一行接口调用日志。
    """
    order_number = _clean(check_num)
    actor = _clean(username)
    paths = [_clean(path) for path in file_paths if _clean(path)]
    if not order_number:
        return "SRM 已提交，但缺少 SDMS 对账单号，发票未传到 SDMS"
    if not actor:
        return "SRM 已提交，但缺少当前登录工号，发票未传到 SDMS"
    if not paths:
        return "SRM 已提交，但没有可上传的发票文件，发票未传到 SDMS"

    base_url = settings.SDMS_ATTACHMENT_API_BASE_URL.rstrip("/")
    errors: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT_SECONDS, trust_env=False) as client:
            for raw_path in paths:
                error = await _upload_one(
                    client,
                    base_url=base_url,
                    flag=STATEMENT_ATTACHMENT_FLAG,
                    order_number=order_number,
                    username=actor,
                    file_path=raw_path,
                    db=db,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    run_id=run_id,
                )
                if error:
                    errors.append(error)
    except httpx.HTTPError as exc:
        logger.warning("sdms statement attachment http failed: %s", type(exc).__name__)
        return f"SRM 已提交，发票传到 SDMS 失败：{type(exc).__name__}"

    if not errors:
        return None
    detail = "；".join(errors[:3])
    return f"SRM 已提交，部分发票未传到 SDMS：{detail}"


async def _upload_one(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    flag: str,
    order_number: str,
    username: str,
    file_path: str,
    db: "AsyncSession | None" = None,
    task_id: str | None = None,
    tenant_id: str | None = None,
    run_id: str | None = None,
) -> str | None:
    path = Path(file_path)
    name = path.name or "invoice"
    try:
        content = path.read_bytes()
    except OSError:
        await _record_upload_call(
            db, task_id, tenant_id, run_id, name, f"{base_url}/upload",
            request_body=None, response_or_exc=None,
            status_code=None, error_code="FILE_READ_ERROR",
        )
        return f"{name} 无法读取"
    if not content:
        await _record_upload_call(
            db, task_id, tenant_id, run_id, name, f"{base_url}/upload",
            request_body=None, response_or_exc=None,
            status_code=None, error_code="FILE_EMPTY",
        )
        return f"{name} 为空"
    if len(content) > MAX_ATTACHMENT_BYTES:
        await _record_upload_call(
            db, task_id, tenant_id, run_id, name, f"{base_url}/upload",
            request_body=None, response_or_exc=None,
            status_code=None, error_code="FILE_TOO_LARGE",
        )
        return f"{name} 超过 20MB"

    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    request_data = {
        "flag": flag,
        "order_number": order_number,
        "username": username,
        "filename": name,
    }
    upload_url = f"{base_url}/upload"
    try:
        response = await client.post(
            upload_url,
            headers={"Accept": "application/json"},
            data=request_data,
            files={"file": (name, content, content_type)},
        )
    except httpx.HTTPError as exc:
        logger.warning("sdms statement attachment upload failed: %s", type(exc).__name__)
        await _record_upload_call(
            db, task_id, tenant_id, run_id, name, upload_url,
            request_body=str(request_data), response_or_exc=exc,
            status_code=None, error_code="NETWORK_ERROR",
        )
        return f"{name} 网络失败"

    error_code: str | None = None
    error_msg: str | None = None
    if response.status_code >= 400:
        error_msg = f"{name} HTTP {response.status_code}"
        error_code = f"HTTP_{response.status_code}"
    else:
        try:
            payload = response.json()
        except ValueError:
            error_msg = f"{name} 响应不是 JSON"
            error_code = "INVALID_JSON"
            payload = None
        else:
            if not isinstance(payload, dict) or not _is_success_code(payload.get("code")):
                error_msg = f"{name} 被附件服务拒绝"
                error_code = "REJECTED"

    await _record_upload_call(
        db, task_id, tenant_id, run_id, name, upload_url,
        request_body=str(request_data), response_or_exc=response,
        status_code=response.status_code, error_code=error_code,
    )
    return error_msg


async def _record_upload_call(
    db: "AsyncSession | None",
    task_id: str | None,
    tenant_id: str | None,
    run_id: str | None,
    name: str,
    url: str,
    *,
    request_body: str | None,
    response_or_exc: Any,
    status_code: int | None,
    error_code: str | None,
) -> None:
    """记录一次上传调用。db 或 task_id 缺失时静默跳过。"""
    from app.services.integration_call_log_service import record_httpx_exchange

    try:
        await record_httpx_exchange(
            db,
            task_id=task_id,
            tenant_id=tenant_id,
            run_id=run_id,
            system="SDMS",
            method="POST",
            url=url,
            request_body=request_body,
            response_or_exc=response_or_exc,
            status_code=status_code,
            error_code=error_code,
        )
    except Exception:  # noqa: BLE001  记录失败不挡业务
        logger.warning("record sdms attachment call failed: %s", name)
