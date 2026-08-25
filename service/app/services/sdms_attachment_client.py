"""把发票文件挂到 SDMS 对账单（HTTP 附件服务，非 RPA）。"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

import httpx

from app.core.config import settings

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
) -> str | None:
    """逐个上传。全部成功返回 None；否则返回可展示给客服的原因。不抛业务异常。"""
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
) -> str | None:
    path = Path(file_path)
    name = path.name or "invoice"
    try:
        content = path.read_bytes()
    except OSError:
        return f"{name} 无法读取"
    if not content:
        return f"{name} 为空"
    if len(content) > MAX_ATTACHMENT_BYTES:
        return f"{name} 超过 20MB"

    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    try:
        response = await client.post(
            f"{base_url}/upload",
            headers={"Accept": "application/json"},
            data={
                "flag": flag,
                "order_number": order_number,
                "username": username,
                "filename": name,
            },
            files={"file": (name, content, content_type)},
        )
    except httpx.HTTPError as exc:
        logger.warning("sdms statement attachment upload failed: %s", type(exc).__name__)
        return f"{name} 网络失败"

    if response.status_code >= 400:
        return f"{name} HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return f"{name} 响应不是 JSON"
    if not isinstance(payload, dict) or not _is_success_code(payload.get("code")):
        return f"{name} 被附件服务拒绝"
    return None
