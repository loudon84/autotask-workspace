"""Portal account CRUD."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
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
    PortalTestOpenResponse,
)
from app.services import audit_service
from app.services.json_utils import dumps_json
from app.services.permission_service import list_accessible_portal_ids

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
    entity_type: str,
    portal_url: str,
    login_account: str,
    exclude_id: str | None = None,
) -> None:
    query = select(PortalAccount).where(
        PortalAccount.tenant_id == tenant_id,
        PortalAccount.entity_type == entity_type,
        PortalAccount.portal_url == portal_url,
        PortalAccount.login_account == login_account,
        not_deleted(PortalAccount),
    )
    if exclude_id:
        query = query.where(PortalAccount.id != exclude_id)
    existing = (await db.execute(query)).scalar_one_or_none()
    if existing:
        raise ConflictError(
            message="门户账号已存在",
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
        items=[PortalAccountResponse.model_validate(account) for account in accounts],
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
) -> PortalAccount:
    entity_type = body.entity_type.value if hasattr(body.entity_type, "value") else body.entity_type
    status = body.status.value if hasattr(body.status, "value") else body.status
    client_open_mode = (
        body.client_open_mode.value if hasattr(body.client_open_mode, "value") else body.client_open_mode
    )

    await _check_portal_uniqueness(
        db,
        tenant_id,
        entity_type,
        body.portal_url,
        body.login_account,
    )

    account_id = str(uuid.uuid4())
    client_session_partition = body.client_session_partition.strip() or f"persist:portal-{account_id}"

    account = PortalAccount(
        id=account_id,
        tenant_id=tenant_id,
        entity_type=entity_type,
        erp_entity_code=body.erp_entity_code,
        erp_entity_name=body.erp_entity_name,
        portal_name=body.portal_name,
        portal_url=body.portal_url,
        login_account=body.login_account,
        credential_ref=body.credential_ref,
        client_open_mode=client_open_mode,
        client_session_partition=client_session_partition,
        rpa_profile_id=body.rpa_profile_id,
        status=status,
        owner_dept_id=body.owner_dept_id,
        created_by=user.user_id,
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
) -> PortalAccount:
    account = await get_portal_account(db, tenant_id, account_id)
    previous_status = account.status
    updates = body.model_dump(exclude_unset=True, by_alias=False)

    next_entity_type = updates.get("entity_type", account.entity_type)
    if hasattr(next_entity_type, "value"):
        next_entity_type = next_entity_type.value
    next_portal_url = updates.get("portal_url", account.portal_url)
    next_login_account = updates.get("login_account", account.login_account)

    if (
        next_entity_type != account.entity_type
        or next_portal_url != account.portal_url
        or next_login_account != account.login_account
    ):
        await _check_portal_uniqueness(
            db,
            tenant_id,
            next_entity_type,
            next_portal_url,
            next_login_account,
            exclude_id=account.id,
        )

    changed_fields: dict[str, dict[str, str]] = {}
    for field, value in updates.items():
        if hasattr(value, "value"):
            value = value.value
        old_value = getattr(account, field)
        if old_value != value:
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
