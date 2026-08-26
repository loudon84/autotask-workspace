"""Sync user profile from nodeskclaw-backend."""

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.models.base import not_deleted
from app.models.user_cache import UserCache
from app.services.json_utils import dumps_json
from app.services.permission_service import extract_managed_user_ids

logger = logging.getLogger(__name__)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _is_cache_stale(synced_at: datetime) -> bool:
    ttl = timedelta(minutes=settings.USER_CACHE_TTL_MINUTES)
    return datetime.now(UTC) - _aware(synced_at) > ttl


def _token_issued_after_cache(issued_at: object, synced_at: datetime) -> bool:
    if issued_at is None:
        return False
    try:
        token_dt = datetime.fromtimestamp(float(issued_at), tz=UTC)
    except (TypeError, ValueError):
        return False
    return token_dt > _aware(synced_at)


def _should_refresh_user_cache(
    cached: UserCache | None,
    *,
    force: bool = False,
    issued_at: object = None,
) -> bool:
    if cached is None or force:
        return True
    if _token_issued_after_cache(issued_at, cached.synced_at):
        return True
    return _is_cache_stale(cached.synced_at)


def _auth_flag(user_data: dict, *keys: str) -> bool:
    for key in keys:
        if key not in user_data:
            continue
        value = user_data[key]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)
    return False


def _unwrap_auth_user(body: object) -> dict:
    """Auth /me 可能是 data 扁平用户，也可能是 data.user / user 包一层。"""
    if not isinstance(body, dict):
        return {}
    payload = body.get("data") if body.get("data") is not None else body
    if not isinstance(payload, dict):
        return body
    nested = payload.get("user")
    if isinstance(nested, dict):
        return {**payload, **nested}
    return payload


async def _fetch_user_from_backend(token: str) -> dict:
    url = f"{settings.NODESKCLAW_BACKEND_URL.rstrip('/')}{settings.NODESKCLAW_AUTH_ME_PATH}"
    async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if response.status_code == 401:
        raise ForbiddenError(
            message="Token 无效或已过期",
            message_key="errors.auth.token_invalid_or_expired",
        )
    if response.status_code >= 400:
        logger.warning("auth/me failed: status=%s body=%s", response.status_code, response.text[:200])
        raise ForbiddenError(
            message="无法从认证服务获取用户信息",
            message_key="errors.auth.user_sync_failed",
        )
    return _unwrap_auth_user(response.json())


def _upsert_user_cache(
    existing: UserCache | None, user_data: dict, managed_ids: list[str]
) -> UserCache:
    now = datetime.now(UTC)
    org_role = user_data.get("org_role") or user_data.get("role")
    fields = {
        "name": user_data.get("name") or "",
        "email": user_data.get("email"),
        "current_org_id": user_data.get("current_org_id"),
        "org_role": org_role,
        "portal_org_role": user_data.get("portal_org_role"),
        "is_super_admin": _auth_flag(user_data, "is_super_admin", "isSuperAdmin"),
        "is_task_admin": _auth_flag(user_data, "is_task_admin", "isTaskAdmin"),
        "managed_user_ids": dumps_json(managed_ids),
        "synced_at": now,
    }
    if existing is None:
        return UserCache(user_id=str(user_data["id"]), **fields)
    for key, value in fields.items():
        setattr(existing, key, value)
    return existing


async def sync_user_from_token(
    db: AsyncSession,
    user_id: str,
    token: str,
    *,
    force: bool = False,
    issued_at: object = None,
) -> UserCache:
    result = await db.execute(
        select(UserCache).where(UserCache.user_id == user_id, not_deleted(UserCache))
    )
    cached = result.scalar_one_or_none()
    if not _should_refresh_user_cache(cached, force=force, issued_at=issued_at):
        return cached

    user_data = await _fetch_user_from_backend(token)
    if str(user_data.get("id")) != user_id:
        user_data["id"] = user_id
    if not user_data.get("is_active", True):
        raise ForbiddenError(
            message="用户不存在或已禁用",
            message_key="errors.auth.user_not_found_or_disabled",
        )

    managed_ids = await _load_managed_user_ids(token, user_id, user_data)
    entity = _upsert_user_cache(cached, user_data, managed_ids)
    if cached is None:
        db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return entity


async def _load_managed_user_ids(token: str, user_id: str, user_data: dict) -> list[str]:
    fallback = extract_managed_user_ids(user_data)
    subordinates = await fetch_subordinates(token, user_id)
    if subordinates is None:
        return fallback
    return [item["user_id"] for item in subordinates]


async def resolve_login_username(token: str | None, user: UserCache) -> str:
    """Auth 登录账号（工号）：优先 /me.username，否则 UserCache.name。"""
    if token:
        try:
            user_data = await _fetch_user_from_backend(token)
            username = str(user_data.get("username") or "").strip()
            if username:
                return username
            name = str(user_data.get("name") or "").strip()
            if name:
                return name
        except Exception:
            logger.info("resolve_login_username fallback to user cache name")
    return str(user.name or "").strip()


async def username_from_user_cache(db: AsyncSession, user_id: str | None) -> str:
    """用 UserCache.name 作为工号回退（无 /me 时，如回签轮询）。"""
    actor = str(user_id or "").strip()
    if not actor:
        return ""
    cached = (
        await db.execute(
            select(UserCache).where(UserCache.user_id == actor, not_deleted(UserCache))
        )
    ).scalar_one_or_none()
    if cached is None:
        return ""
    return str(cached.name or "").strip()


def _first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _parse_auth_people(payload: object) -> list[dict[str, str]]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        data = data.get("items") or data.get("members") or data.get("list") or []
    if not isinstance(data, list):
        return []
    people: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        user = item.get("user") if isinstance(item.get("user"), dict) else item
        member_id = _first_text(
            user.get("user_id"),
            user.get("userId"),
            item.get("user_id"),
            item.get("userId"),
            user.get("id"),
            item.get("id"),
        )
        if not member_id or member_id in seen:
            continue
        seen.add(member_id)
        people.append(
            {
                "user_id": member_id,
                "name": _first_text(
                    user.get("name"),
                    user.get("user_name"),
                    user.get("userName"),
                    user.get("display_name"),
                    user.get("displayName"),
                    item.get("name"),
                    item.get("user_name"),
                ),
                "username": _first_text(
                    user.get("username"),
                    user.get("employee_no"),
                    user.get("employeeNo"),
                    item.get("username"),
                    item.get("employee_no"),
                ),
            }
        )
    return people


async def fetch_subordinates(token: str, user_id: str) -> list[dict[str, str]] | None:
    """登录人下属。失败返回 None（保留 /me 回退）；成功无下属返回 []。"""
    actor = str(user_id or "").strip()
    if not actor or not token:
        return None
    url = (
        f"{settings.NODESKCLAW_BACKEND_URL.rstrip('/')}"
        f"/api/v1/members/{actor}/subordinate"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    except Exception:
        logger.warning("fetch subordinates failed for %s", actor, exc_info=True)
        return None
    if response.status_code >= 400:
        logger.warning(
            "subordinates failed: status=%s body=%s",
            response.status_code,
            response.text[:200],
        )
        return None
    return _parse_auth_people(response.json())


async def fetch_org_members(token: str, org_id: str) -> list[dict[str, str]]:
    """组织成员，给 admin 归属人下拉用。Auth 接口形态做宽松解析。"""
    org = str(org_id or "").strip()
    if not org or not token:
        return []
    url = f"{settings.NODESKCLAW_BACKEND_URL.rstrip('/')}/api/v1/orgs/{org}/members"
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    except Exception:
        logger.warning("fetch org members failed for org %s", org, exc_info=True)
        return []
    if response.status_code >= 400:
        logger.warning(
            "org members failed: status=%s body=%s",
            response.status_code,
            response.text[:200],
        )
        return []
    return _parse_auth_people(response.json())


async def refresh_user_cache_background(user_id: str, token: str) -> None:
    from app.core.deps import async_session_factory

    try:
        async with async_session_factory() as db:
            await sync_user_from_token(db, user_id, token)
    except Exception:
        logger.warning("background user cache refresh failed for %s", user_id, exc_info=True)
