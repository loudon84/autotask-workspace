"""Portal account CRUD."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.enums import PortalAccountStatus, PortalPermission
from app.models.portal_access_grant import PortalAccessGrant
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache
from app.schemas.portal_account import (
    PortalAccessGrantCreate,
    PortalAccountCreate,
    PortalAccountResponse,
    PortalAccountUpdate,
    PortalListPageResponse,
    PortalOwnerCandidate,
    PortalTestOpenResponse,
)
from app.services import audit_service
from app.services.json_utils import dumps_json
from app.services.permission_service import (
    effective_owner_user_id,
    is_scope_admin,
    list_accessible_portal_ids,
)
from app.services.user_sync import fetch_subordinates

_DEFAULT_CREATOR_PERMISSIONS = [
    PortalPermission.PORTAL_VIEW,
    PortalPermission.PORTAL_EDIT,
    PortalPermission.PORTAL_OPEN_WEB,
    PortalPermission.PORTAL_MANAGE_PERMISSION,
    PortalPermission.PORTAL_BIND_WORKFLOW,
    PortalPermission.PORTAL_VIEW_TASKS,
]


async def _check_portal_uniqueness(
    db: AsyncSession,
    tenant_id: str,
    portal_name: str,
    exclude_id: str | None = None,
) -> None:
    query = select(PortalAccount).where(
        PortalAccount.tenant_id == tenant_id,
        PortalAccount.portal_name == portal_name,
        not_deleted(PortalAccount),
    )
    if exclude_id:
        query = query.where(PortalAccount.id != exclude_id)
    existing = (await db.execute(query)).scalar_one_or_none()
    if existing:
        raise ConflictError(
            message="门户名称已存在",
            message_key="errors.autotask.portal_account.duplicate",
        )


def _apply_keyword_filter(query, keyword: str | None):
    if not keyword:
        return query
    pattern = f"%{keyword.strip()}%"
    return query.where(
        or_(
            PortalAccount.erp_entity_name.ilike(pattern),
            PortalAccount.portal_name.ilike(pattern),
            PortalAccount.login_account.ilike(pattern),
            PortalAccount.portal_url.ilike(pattern),
        )
    )


def _actor_display_name(user: UserCache) -> str:
    return str(user.name or "").strip()


def _to_portal_response(account: PortalAccount) -> PortalAccountResponse:
    owner_id = effective_owner_user_id(account)
    payload = PortalAccountResponse.model_validate(account)
    return payload.model_copy(
        update={
            "owner_user_id": owner_id,
            "owner_name": str(getattr(account, "owner_user_name", None) or ""),
            "created_by_name": str(getattr(account, "created_by_name", None) or ""),
            "owner_username": "",
        }
    )


async def build_portal_response(
    db: AsyncSession,
    account: PortalAccount,
) -> PortalAccountResponse:
    _ = db
    return _to_portal_response(account)


def _owner_candidates_from_people(
    people: list[dict[str, str]],
    user: UserCache,
) -> list[PortalOwnerCandidate]:
    candidates: list[PortalOwnerCandidate] = []
    seen: set[str] = set()
    for item in people:
        member_id = str(item.get("user_id") or "").strip()
        if not member_id or member_id in seen:
            continue
        seen.add(member_id)
        candidates.append(
            PortalOwnerCandidate(
                user_id=member_id,
                name=item.get("name") or "",
                username=item.get("username") or "",
            )
        )
    if user.user_id not in seen:
        candidates.insert(
            0,
            PortalOwnerCandidate(
                user_id=user.user_id,
                name=user.name or "",
                username="",
            ),
        )
    return candidates


async def list_owner_candidates(
    db: AsyncSession,
    user: UserCache,
    token: str | None = None,
) -> list[PortalOwnerCandidate]:
    """归属人下拉现拉下属接口。Auth 已按角色返回全员/自己/自己+下属。不读登录缓存。"""
    _ = db
    people: list[dict[str, str]] = []
    if token:
        fetched = await fetch_subordinates(token, user.user_id)
        if fetched is not None:
            people = fetched
    return _owner_candidates_from_people(people, user)


def _person_from_owner(
    people: list[dict[str, str]],
    user: UserCache,
    owner_user_id: str,
) -> dict[str, str]:
    for item in people:
        if item.get("user_id") == owner_user_id:
            return item
    if owner_user_id == user.user_id:
        return {"user_id": user.user_id, "name": user.name or "", "username": ""}
    return {"user_id": owner_user_id, "name": "", "username": ""}


async def _assert_owner_candidate(
    db: AsyncSession,
    user: UserCache,
    owner_user_id: str,
    token: str | None = None,
) -> dict[str, str]:
    _ = db
    fetched = None
    if token:
        fetched = await fetch_subordinates(token, user.user_id)
    if fetched is not None:
        allowed = {item["user_id"] for item in fetched}
        allowed.add(user.user_id)
        if owner_user_id not in allowed:
            raise ForbiddenError(
                message="不能把门户转给该用户",
                message_key="errors.autotask.portal_owner_not_allowed",
            )
        return _person_from_owner(fetched, user, owner_user_id)
    if is_scope_admin(user) or owner_user_id == user.user_id:
        return _person_from_owner([], user, owner_user_id)
    raise ForbiddenError(
        message="不能把门户转给该用户",
        message_key="errors.autotask.portal_owner_not_allowed",
    )


async def list_portal_accounts(
    db: AsyncSession,
    tenant_id: str,
    user: UserCache,
    *,
    entity_type: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PortalListPageResponse:
    current_page = max(page, 1)
    size = max(min(page_size, 100), 1)

    query = select(PortalAccount).where(
        PortalAccount.tenant_id == tenant_id,
        not_deleted(PortalAccount),
    )
    if entity_type:
        query = query.where(PortalAccount.entity_type == entity_type)
    if status:
        query = query.where(PortalAccount.status == status)

    accessible_ids = await list_accessible_portal_ids(
        db,
        user,
        tenant_id,
        PortalPermission.PORTAL_VIEW,
    )
    if accessible_ids is not None:
        if not accessible_ids:
            return PortalListPageResponse(items=[], total=0, page=current_page, page_size=size)
        query = query.where(PortalAccount.id.in_(accessible_ids))

    query = _apply_keyword_filter(query, keyword)

    count_query = select(func.count()).select_from(query.subquery())
    total = int((await db.execute(count_query)).scalar_one())

    result = await db.execute(
        query.order_by(PortalAccount.created_at.desc())
        .offset((current_page - 1) * size)
        .limit(size)
    )
    accounts = list(result.scalars().all())
    return PortalListPageResponse(
        items=[_to_portal_response(account) for account in accounts],
        total=total,
        page=current_page,
        page_size=size,
    )


async def get_portal_account(db: AsyncSession, tenant_id: str, account_id: str) -> PortalAccount:
    account = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == account_id,
                PortalAccount.tenant_id == tenant_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise NotFoundError(message="Portal 账号不存在", message_key="errors.autotask.portal_not_found")
    return account


async def create_portal_account(
    db: AsyncSession,
    tenant_id: str,
    user: UserCache,
    body: PortalAccountCreate,
    token: str | None = None,
) -> PortalAccount:
    entity_type = body.entity_type.value if hasattr(body.entity_type, "value") else body.entity_type
    status = body.status.value if hasattr(body.status, "value") else body.status
    client_open_mode = (
        body.client_open_mode.value if hasattr(body.client_open_mode, "value") else body.client_open_mode
    )

    await _check_portal_uniqueness(
        db,
        tenant_id,
        body.portal_name,
    )

    account_id = str(uuid.uuid4())
    client_session_partition = body.client_session_partition.strip() or f"persist:portal-{account_id}"

    owner_id = str(body.owner_user_id or "").strip() or user.user_id
    if owner_id != user.user_id:
        await _assert_owner_candidate(db, user, owner_id, token)
    owner_name = str(body.owner_user_name or "").strip()
    if not owner_name and owner_id == user.user_id:
        owner_name = _actor_display_name(user)
    created_name = str(body.created_by_name or "").strip() or _actor_display_name(user)

    account = PortalAccount(
        id=account_id,
        tenant_id=tenant_id,
        entity_type=entity_type,
        erp_entity_code=body.erp_entity_code,
        erp_entity_name=body.erp_entity_name,
        business_entity=(body.business_entity or "").strip(),
        ou=(body.ou or "").strip(),
        category=body.category,
        portal_name=body.portal_name,
        portal_url=body.portal_url,
        login_account=body.login_account,
        credential_ref=body.credential_ref,
        client_open_mode=client_open_mode,
        client_session_partition=client_session_partition,
        rpa_profile_id=body.rpa_profile_id,
        status=status,
        owner_dept_id=body.owner_dept_id,
        owner_user_id=owner_id,
        owner_user_name=owner_name,
        created_by=user.user_id,
        created_by_name=created_name,
    )

    db.add(account)
    db.add(
        PortalAccessGrant(
            portal_account_id=account_id,
            subject_type="USER",
            subject_id=user.user_id,
            permissions=dumps_json([permission.value for permission in _DEFAULT_CREATOR_PERMISSIONS]),
            granted_by=user.user_id,
            granted_at=datetime.now(UTC).isoformat(),
        )
    )
    await audit_service.write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=user.user_id,
        action=audit_service.ACTION_PORTAL_CREATED,
        resource_type=audit_service.PORTAL_ACCOUNT_RESOURCE_TYPE,
        resource_id=account_id,
        details={
            "portalName": account.portal_name,
            "portalUrl": account.portal_url,
            "loginAccount": account.login_account,
        },
    )
    await db.commit()
    await db.refresh(account)
    return account


async def update_portal_account(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    body: PortalAccountUpdate,
    actor: UserCache,
    token: str | None = None,
) -> PortalAccount:
    account = await get_portal_account(db, tenant_id, account_id)
    previous_status = account.status
    updates = body.model_dump(exclude_unset=True, by_alias=False)
    if "owner_user_id" in updates:
        next_owner = str(updates.get("owner_user_id") or "").strip()
        if not next_owner:
            updates.pop("owner_user_id")
        else:
            updates["owner_user_id"] = next_owner
            await _assert_owner_candidate(db, actor, next_owner, token)
    if "owner_user_name" in updates:
        next_name = str(updates.get("owner_user_name") or "").strip()
        if next_name:
            updates["owner_user_name"] = next_name
        else:
            updates.pop("owner_user_name")
    updates.pop("created_by_name", None)
    if "credential_ref" in updates and not str(updates.get("credential_ref") or "").strip():
        updates.pop("credential_ref")
    for key in ("business_entity", "ou"):
        if key in updates:
            updates[key] = str(updates.get(key) or "").strip()

    next_portal_name = updates.get("portal_name", account.portal_name)

    if next_portal_name != account.portal_name:
        await _check_portal_uniqueness(
            db,
            tenant_id,
            next_portal_name,
            exclude_id=account.id,
        )

    changed_fields: dict[str, dict[str, str]] = {}
    for field, value in updates.items():
        if hasattr(value, "value"):
            value = value.value
        old_value = getattr(account, field)
        if old_value != value:
            if field == "credential_ref":
                changed_fields[field] = {"from": "***", "to": "***"}
            else:
                changed_fields[field] = {"from": str(old_value), "to": str(value)}
        setattr(account, field, value)

    if previous_status != PortalAccountStatus.DISABLED.value and account.status == PortalAccountStatus.DISABLED.value:
        await audit_service.write_audit_log(
            db,
            tenant_id=tenant_id,
            actor_id=actor.user_id,
            action=audit_service.ACTION_PORTAL_DISABLED,
            resource_type=audit_service.PORTAL_ACCOUNT_RESOURCE_TYPE,
            resource_id=account.id,
            details={"portalName": account.portal_name},
        )

    if changed_fields:
        await audit_service.write_audit_log(
            db,
            tenant_id=tenant_id,
            actor_id=actor.user_id,
            action=audit_service.ACTION_PORTAL_UPDATED,
            resource_type=audit_service.PORTAL_ACCOUNT_RESOURCE_TYPE,
            resource_id=account.id,
            details={"changedFields": changed_fields},
        )

    await db.commit()
    await db.refresh(account)
    return account


async def delete_portal_account(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    actor: UserCache,
) -> None:
    account = await get_portal_account(db, tenant_id, account_id)
    grants = (
        await db.execute(
            select(PortalAccessGrant).where(
                PortalAccessGrant.portal_account_id == account_id,
                not_deleted(PortalAccessGrant),
            )
        )
    ).scalars().all()
    for grant in grants:
        grant.soft_delete()

    account.soft_delete()
    await audit_service.write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=actor.user_id,
        action=audit_service.ACTION_PORTAL_DELETED,
        resource_type=audit_service.PORTAL_ACCOUNT_RESOURCE_TYPE,
        resource_id=account.id,
        details={"portalName": account.portal_name},
    )
    await db.commit()


async def test_open_portal_account(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    actor: UserCache,
) -> PortalTestOpenResponse:
    account = await get_portal_account(db, tenant_id, account_id)
    if account.status != PortalAccountStatus.ENABLED.value:
        raise BadRequestError(
            message="Portal 账号已禁用，无法打开",
            message_key="errors.autotask.portal_account.disabled",
        )

    await audit_service.write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=actor.user_id,
        action=audit_service.ACTION_PORTAL_OPENED,
        resource_type=audit_service.PORTAL_ACCOUNT_RESOURCE_TYPE,
        resource_id=account.id,
        details={"portalName": account.portal_name, "portalUrl": account.portal_url},
    )
    await db.commit()

    return PortalTestOpenResponse(
        portal_account_id=account.id,
        portal_name=account.portal_name,
        portal_url=account.portal_url,
        client_open_mode=account.client_open_mode,
        client_session_partition=account.client_session_partition,
        status=account.status,
        allowed=True,
    )


async def list_access_grants(db: AsyncSession, tenant_id: str, account_id: str) -> list[PortalAccessGrant]:
    await get_portal_account(db, tenant_id, account_id)
    result = await db.execute(
        select(PortalAccessGrant).where(
            PortalAccessGrant.portal_account_id == account_id,
            not_deleted(PortalAccessGrant),
        )
    )
    return list(result.scalars().all())


async def create_access_grant(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    user: UserCache,
    body: PortalAccessGrantCreate,
) -> PortalAccessGrant:
    await get_portal_account(db, tenant_id, account_id)
    grant = PortalAccessGrant(
        portal_account_id=account_id,
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        permissions=dumps_json(body.permissions),
        granted_by=user.user_id,
        granted_at=datetime.now(UTC).isoformat(),
    )
    db.add(grant)
    await audit_service.write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=user.user_id,
        action=audit_service.ACTION_PORTAL_ACCESS_GRANTED,
        resource_type=audit_service.PORTAL_ACCOUNT_RESOURCE_TYPE,
        resource_id=account_id,
        details={
            "grantId": grant.id,
            "subjectType": body.subject_type,
            "subjectId": body.subject_id,
            "permissions": body.permissions,
        },
    )
    await db.commit()
    await db.refresh(grant)
    return grant
