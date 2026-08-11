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

logger = logging.getLogger(__name__)


def _is_cache_stale(synced_at: datetime) -> bool:
    ttl = timedelta(minutes=settings.USER_CACHE_TTL_MINUTES)
    now = datetime.now(UTC)
    synced = synced_at if synced_at.tzinfo else synced_at.replace(tzinfo=UTC)
    return now - synced > ttl


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
    body = response.json()
    return body.get("data") or body


def _upsert_user_cache(existing: UserCache | None, user_data: dict) -> UserCache:
    now = datetime.now(UTC)
    org_role = user_data.get("org_role") or user_data.get("role")
    fields = {
        "name": user_data.get("name") or "",
        "email": user_data.get("email"),
        "current_org_id": user_data.get("current_org_id"),
        "org_role": org_role,
        "portal_org_role": user_data.get("portal_org_role"),
        "is_super_admin": bool(user_data.get("is_super_admin")),
        "synced_at": now,
    }
    if existing is None:
        return UserCache(user_id=str(user_data["id"]), **fields)
    for key, value in fields.items():
        setattr(existing, key, value)
    return existing


async def sync_user_from_token(db: AsyncSession, user_id: str, token: str) -> UserCache:
    result = await db.execute(
        select(UserCache).where(UserCache.user_id == user_id, not_deleted(UserCache))
    )
    cached = result.scalar_one_or_none()
    if cached is not None and not _is_cache_stale(cached.synced_at):
        return cached

    user_data = await _fetch_user_from_backend(token)
    if str(user_data.get("id")) != user_id:
        user_data["id"] = user_id
    if not user_data.get("is_active", True):
        raise ForbiddenError(
            message="用户不存在或已禁用",
            message_key="errors.auth.user_not_found_or_disabled",
        )

    entity = _upsert_user_cache(cached, user_data)
    if cached is None:
        db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return entity


async def refresh_user_cache_background(user_id: str, token: str) -> None:
    from app.core.deps import async_session_factory

    try:
        async with async_session_factory() as db:
            await sync_user_from_token(db, user_id, token)
    except Exception:
        logger.warning("background user cache refresh failed for %s", user_id, exc_info=True)
