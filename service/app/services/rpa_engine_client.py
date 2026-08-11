"""RPA Engine HTTP client."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestError


def normalize_checksum(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().lower()
    if value.startswith("sha256:"):
        value = value[7:]
    return value


async def validate_binding(
    *,
    rpa_flow_id: str,
    rpa_flow_version: str,
    workflow_code: str,
    actor_id: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    if not settings.RPA_ENGINE_VALIDATE_BINDING:
        return {
            "valid": True,
            "rpaFlowVersionId": f"seed-version-{rpa_flow_id}",
            "checksum": "0" * 64,
        }

    if not settings.RPA_ENGINE_BASE_URL:
        raise BadRequestError(
            message="未配置 RPA Engine 地址，无法校验 Flow 绑定",
            message_key="errors.autotask.rpa_engine_not_configured",
        )

    url = f"{settings.RPA_ENGINE_BASE_URL.rstrip('/')}/api/v1/flow-versions/validate-binding"
    headers = {"X-Actor-Id": actor_id, "Content-Type": "application/json"}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id

    body = {
        "rpaFlowId": rpa_flow_id,
        "rpaFlowVersion": rpa_flow_version,
        "workflowCode": workflow_code,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise BadRequestError(
            message=f"RPA Engine 校验绑定失败: {exc}",
            message_key="errors.autotask.binding_validate_failed",
        ) from exc

    payload = data.get("data", data) if isinstance(data, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    if not payload.get("valid", False):
        raise BadRequestError(
            message="RPA Flow 版本校验未通过，仅允许绑定已发布且有效的版本",
            message_key="errors.autotask.binding_flow_invalid",
        )

    version_id = payload.get("rpaFlowVersionId") or payload.get("rpa_flow_version_id")
    checksum = normalize_checksum(payload.get("checksum") or payload.get("flowChecksum"))
    if not version_id or not checksum:
        raise BadRequestError(
            message="RPA Engine 未返回版本 ID 或 checksum",
            message_key="errors.autotask.binding_flow_snapshot_incomplete",
        )
    return {
        "valid": True,
        "rpaFlowVersionId": version_id,
        "checksum": checksum,
    }
