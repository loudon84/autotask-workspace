"""环境级外部系统基址。换测试/正式只改 Task .env，不写 Binding。"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

# 对账单查询挂在 SMC 接口平台，不是 SDMS 网页主机。
SDMS_CHECK_PATH = "/sdms/ar_check/view_doc_srm"


def _base(value: str | None) -> str:
    return str(value or "").strip().rstrip("/")


def join_url(base: str, path: str) -> str:
    return f"{_base(base)}/{str(path).lstrip('/')}"


def sdms_check_url() -> str:
    """对账单金额查询：SMC_API_BASE_URL + 固定路径。"""
    base = _base(settings.SMC_API_BASE_URL)
    if not base:
        return ""
    return join_url(base, SDMS_CHECK_PATH)


def client_integration_endpoints() -> dict[str, str]:
    """给已登录 Client 打开 SDMS 网页链接。不含 OAuth 密钥。"""
    return {"sdmsBaseUrl": _base(settings.SDMS_BASE_URL)}


def integration_lease_config() -> dict[str, Any]:
    """租约 config：只带基址和客户端密钥，路径由 Flow 拼接。"""
    payload: dict[str, Any] = {}
    sdms = _base(settings.SDMS_BASE_URL)
    erp = _base(settings.ERP_BASE_URL)
    oa = _base(settings.OA_BASE_URL)
    doc = _base(settings.SDMS_ATTACHMENT_API_BASE_URL)
    if sdms:
        payload["sdmsBaseUrl"] = sdms
    if erp:
        payload["erpBaseUrl"] = erp
    if oa:
        payload["oaBaseUrl"] = oa
    if doc:
        payload["docBaseUrl"] = doc
    client_id = str(settings.ERP_CLIENT_ID or "").strip()
    client_secret = str(settings.ERP_CLIENT_SECRET or "").strip()
    if client_id:
        payload["erpClientId"] = client_id
    if client_secret:
        payload["erpClientSecret"] = client_secret
    return payload
