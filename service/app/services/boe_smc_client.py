"""京东方交货计划 / WMS HTTP（SMC 平台，无认证）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


def _text(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    return str(value).strip()


def _join_url(base: str, path: str) -> str:
    root = (base or "").rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    if not root:
        return suffix
    return f"{root}{suffix}"


@dataclass(frozen=True)
class SmcHttpResult:
    url: str
    status_code: int | None
    body: str
    data: list[dict[str, Any]]
    error: str | None


def _parse_payload(payload: Any) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(payload, dict):
        return [], "响应不是 JSON 对象"
    code = payload.get("code")
    if code not in (1, "1", 0, "0", None):
        msg = _text(payload.get("msg") or payload.get("message")) or f"接口 code={code}"
        return [], msg
    raw = payload.get("data")
    if raw is None:
        return [], None
    if isinstance(raw, dict):
        return [raw], None
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)], None
    return [], "data 不是列表"


async def fetch_delivery_plans() -> SmcHttpResult:
    url = _join_url(settings.SMC_API_BASE_URL, settings.BOE_DELIVERY_PLAN_PATH)
    if not settings.SMC_API_BASE_URL:
        return SmcHttpResult(url=url, status_code=None, body="", data=[], error="未配置 SMC_API_BASE_URL")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url)
        body = response.text
        payload: Any = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        rows, parse_error = _parse_payload(payload)
        error = None if response.is_success else f"HTTP {response.status_code}"
        return SmcHttpResult(
            url=url,
            status_code=response.status_code,
            body=body,
            data=rows,
            error=error or parse_error,
        )
    except httpx.HTTPError as exc:
        return SmcHttpResult(url=url, status_code=None, body="", data=[], error=str(exc))


async def fetch_wms_packing(doc_no: str) -> SmcHttpResult:
    url = _join_url(settings.SMC_API_BASE_URL, settings.BOE_WMS_PATH)
    params = {"doc_no": doc_no}
    if not settings.SMC_API_BASE_URL:
        return SmcHttpResult(url=url, status_code=None, body="", data=[], error="未配置 SMC_API_BASE_URL")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
        body = response.text
        payload: Any = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        rows, parse_error = _parse_payload(payload)
        error = None if response.is_success else f"HTTP {response.status_code}"
        return SmcHttpResult(
            url=str(response.url),
            status_code=response.status_code,
            body=body,
            data=rows,
            error=error or parse_error,
        )
    except httpx.HTTPError as exc:
        return SmcHttpResult(url=url, status_code=None, body="", data=[], error=str(exc))
