"""JWT validation and auth dependencies."""

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.core.exceptions import ForbiddenError
from app.models.user_cache import UserCache
from app.services.permission_service import check_portal_permission
from app.services.user_sync import sync_user_from_token

bearer_scheme = HTTPBearer(auto_error=False)
_ALLOWED_TOKEN_TYPES = {"access"}


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40101,
                "message_key": "errors.auth.token_invalid_or_expired",
                "message": "Token 无效或已过期",
            },
        )


def extract_user_id(payload: dict) -> str:
    if payload.get("type") not in _ALLOWED_TOKEN_TYPES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40102,
                "message_key": "errors.auth.token_type_invalid",
                "message": "Token 类型错误",
            },
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40104,
                "message_key": "errors.auth.token_subject_missing",
                "message": "Token 无效",
            },
        )
    return str(user_id)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserCache:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40100,
                "message_key": "errors.auth.credentials_missing",
                "message": "未提供认证信息",
            },
        )
    payload = decode_token(credentials.credentials)
    user_id = extract_user_id(payload)
    return await sync_user_from_token(db, user_id, credentials.credentials)


def require_tenant_access(user: UserCache) -> str:
    if not user.current_org_id:
        raise ForbiddenError(
            message="用户未加入任何组织，无法访问 AutoTask",
            message_key="errors.org.user_has_no_org",
        )
    return user.current_org_id


async def require_permission(
    db: AsyncSession,
    user: UserCache,
    portal_account_id: str,
    permission: str,
) -> None:
    tenant_id = require_tenant_access(user)
    allowed = await check_portal_permission(db, user, tenant_id, portal_account_id, permission)
    if not allowed:
        raise ForbiddenError(
            message="无权限执行该操作",
            message_key="errors.autotask.permission_denied",
        )


_PORTAL_MANAGE_ROLES = {"admin", "operator"}


def require_portal_manage_access(user: UserCache) -> None:
    require_tenant_access(user)
    if user.is_super_admin:
        return
    if (user.org_role or "") in _PORTAL_MANAGE_ROLES:
        return
    raise ForbiddenError(
        message="无权限管理 Portal 账号",
        message_key="errors.autotask.permission_denied",
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
