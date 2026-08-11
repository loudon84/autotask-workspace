"""Business audit log writes."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.services.json_utils import dumps_json

PORTAL_ACCOUNT_RESOURCE_TYPE = "portal_account"
WORKFLOW_TEMPLATE_RESOURCE_TYPE = "workflow_template"

ACTION_PORTAL_CREATED = "portal_account.created"
ACTION_PORTAL_UPDATED = "portal_account.updated"
ACTION_PORTAL_DISABLED = "portal_account.disabled"
ACTION_PORTAL_DELETED = "portal_account.deleted"
ACTION_PORTAL_OPENED = "portal_account.opened"
ACTION_PORTAL_ACCESS_GRANTED = "portal_account.access_granted"
ACTION_WORKFLOW_TEMPLATE_DELETED = "workflow_template.deleted"


async def write_audit_log(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=dumps_json(details or {}),
        )
    )
