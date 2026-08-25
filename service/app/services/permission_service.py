"""Portal visibility by owner_user_id. Grants are kept but not used for ACL."""

from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache
from app.services.json_utils import loads_json


def is_scope_admin(user: UserCache) -> bool:
    if user.is_super_admin:
        return True
    if getattr(user, "is_task_admin", False):
        return True
    return (user.portal_org_role or "").strip().lower() == "admin"


def parse_managed_user_ids(raw: str | None) -> list[str]:
    data = loads_json(raw, [])
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in data:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ids.append(value)
    return ids


def extract_managed_user_ids(user_data: dict) -> list[str]:
    raw = (
        user_data.get("managed_users")
        or user_data.get("managedUsers")
        or user_data.get("managed_user_ids")
        or user_data.get("managedUserIds")
        or user_data.get("reports")
        or user_data.get("subordinates")
        or []
    )
    ids: list[str] = []
    seen: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            uid = ""
            if isinstance(item, str):
                uid = item.strip()
            elif isinstance(item, dict):
                uid = str(
                    item.get("id")
                    or item.get("user_id")
                    or item.get("userId")
                    or ""
                ).strip()
            if not uid or uid in seen:
                continue
            seen.add(uid)
            ids.append(uid)
    return ids


def visible_owner_ids(user: UserCache) -> set[str]:
    ids = {user.user_id}
    ids.update(parse_managed_user_ids(getattr(user, "managed_user_ids", None)))
    return ids


def effective_owner_user_id(portal: PortalAccount) -> str:
    return str(portal.owner_user_id or portal.created_by or "").strip()


def apply_accessible_portal_filter(query, column: ColumnElement, accessible_ids: list[str] | None):
    if accessible_ids is None:
        return query
    if not accessible_ids:
        return query.where(false())
    return query.where(column.in_(accessible_ids))


async def check_portal_permission(
    db: AsyncSession,
    user: UserCache,
    tenant_id: str,
    portal_account_id: str,
    permission: str,
) -> bool:
    del permission
    if is_scope_admin(user):
        portal = (
            await db.execute(
                select(PortalAccount.id).where(
                    PortalAccount.id == portal_account_id,
                    PortalAccount.tenant_id == tenant_id,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
        return portal is not None

    portal = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == portal_account_id,
                PortalAccount.tenant_id == tenant_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if portal is None:
        return False
    return effective_owner_user_id(portal) in visible_owner_ids(user)


async def list_accessible_portal_ids(
    db: AsyncSession,
    user: UserCache,
    tenant_id: str,
    permission: str,
) -> list[str] | None:
    del permission
    if is_scope_admin(user):
        return None

    owner_ids = visible_owner_ids(user)
    if not owner_ids:
        return []
    result = await db.execute(
        select(PortalAccount.id).where(
            PortalAccount.tenant_id == tenant_id,
            not_deleted(PortalAccount),
            func.coalesce(PortalAccount.owner_user_id, PortalAccount.created_by).in_(owner_ids),
        )
    )
    return list(result.scalars().all())
