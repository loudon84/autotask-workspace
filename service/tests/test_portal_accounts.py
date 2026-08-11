import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError
from app.core.security import require_portal_manage_access
from app.main import app
from app.models.enums import ClientOpenMode, EntityType, PortalAccountStatus
from app.models.user_cache import UserCache
from app.schemas.portal_account import (
    PortalAccountCreate,
    PortalAccountResponse,
    PortalListPageResponse,
    PortalTestOpenResponse,
)
from app.services import portal_account_service


def _user(
    *,
    user_id: str = "user-001",
    org_role: str | None = "admin",
    is_super_admin: bool = False,
    current_org_id: str = "tenant-001",
) -> UserCache:
    return UserCache(
        user_id=user_id,
        name="测试用户",
        email="user@example.com",
        current_org_id=current_org_id,
        org_role=org_role,
        portal_org_role=None,
        is_super_admin=is_super_admin,
        synced_at=datetime.now(UTC),
    )


def _portal_account(**overrides):
    defaults = {
        "id": "portal-001",
        "tenant_id": "tenant-001",
        "entity_type": EntityType.CUSTOMER.value,
        "erp_entity_code": "CUST-001",
        "erp_entity_name": "示例客户 A",
        "portal_name": "客户 SRM 门户",
        "portal_url": "https://portal.example.com/srm",
        "login_account": "buyer@example.com",
        "client_open_mode": ClientOpenMode.WEBCONTENTS.value,
        "client_session_partition": "persist:portal-001",
        "status": PortalAccountStatus.ENABLED.value,
        "created_by": "user-001",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return type("PortalAccountStub", (), defaults)()


def test_portal_account_create_validates_http_url():
    with pytest.raises(ValidationError):
        PortalAccountCreate(
            entityType="CUSTOMER",
            erpEntityCode="CUST-001",
            erpEntityName="示例客户 A",
            portalName="客户 SRM 门户",
            portalUrl="ftp://portal.example.com/srm",
            loginAccount="buyer@example.com",
            clientOpenMode="webcontents",
        )


def test_portal_account_create_requires_non_empty_fields():
    with pytest.raises(ValidationError):
        PortalAccountCreate(
            entityType="CUSTOMER",
            erpEntityCode="",
            erpEntityName="示例客户 A",
            portalName="客户 SRM 门户",
            portalUrl="https://portal.example.com/srm",
            loginAccount="buyer@example.com",
            clientOpenMode="webcontents",
        )


def test_portal_list_page_response_uses_camel_case():
    payload = PortalListPageResponse(
        items=[
            PortalAccountResponse.model_validate(
                _portal_account(),
                from_attributes=True,
            )
        ],
        total=1,
        page=1,
        page_size=20,
    ).model_dump(by_alias=True)
    assert payload["pageSize"] == 20
    assert payload["items"][0]["portalName"] == "客户 SRM 门户"
    assert payload["items"][0]["tenantId"] == "tenant-001"
    assert "credentialRef" not in payload["items"][0]


def test_portal_test_open_response_matches_prd():
    payload = PortalTestOpenResponse(
        portal_account_id="portal-001",
        portal_name="客户 SRM 门户",
        portal_url="https://portal.example.com/srm",
        client_open_mode="webcontents",
        client_session_partition="persist:portal-001",
        status="ENABLED",
        allowed=True,
    ).model_dump(by_alias=True)
    assert payload["allowed"] is True
    assert payload["portalName"] == "客户 SRM 门户"
    assert payload["clientSessionPartition"] == "persist:portal-001"
    assert "canOpen" not in payload


def test_require_portal_manage_access_allows_admin_and_operator():
    require_portal_manage_access(_user(org_role="admin"))
    require_portal_manage_access(_user(org_role="operator"))
    require_portal_manage_access(_user(is_super_admin=True, org_role=None))


def test_require_portal_manage_access_rejects_member():
    with pytest.raises(ForbiddenError):
        require_portal_manage_access(_user(org_role="member"))


@pytest.mark.asyncio
async def test_create_portal_account_uses_explicit_id_for_grant_and_partition():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=type("Result", (), {"scalar_one_or_none": lambda self: None})())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    body = PortalAccountCreate(
        entityType="CUSTOMER",
        erpEntityCode="CUST-010",
        erpEntityName="新客户",
        portalName="新客户 SRM",
        portalUrl="https://portal.example.com/new",
        loginAccount="new@example.com",
        clientOpenMode="webcontents",
    )
    added: list[object] = []
    db.add = lambda obj: added.append(obj)

    with patch("app.services.portal_account_service.audit_service.write_audit_log", new=AsyncMock()):
        account = await portal_account_service.create_portal_account(
            db,
            "tenant-001",
            _user(),
            body,
        )

    assert account.id is not None
    assert account.client_session_partition == f"persist:portal-{account.id}"
    grant = next(item for item in added if item.__class__.__name__ == "PortalAccessGrant")
    assert grant.portal_account_id == account.id


@pytest.mark.asyncio
async def test_test_open_disabled_portal_returns_bad_request():
    db = AsyncMock()
    with patch(
        "app.services.portal_account_service.get_portal_account",
        new=AsyncMock(
            return_value=_portal_account(status=PortalAccountStatus.DISABLED.value),
        ),
    ):
        with pytest.raises(BadRequestError) as exc_info:
            await portal_account_service.test_open_portal_account(
                db,
                "tenant-001",
                "portal-001",
                _user(),
            )
        assert exc_info.value.message_key == "errors.autotask.portal_account.disabled"


@pytest.mark.asyncio
async def test_check_portal_uniqueness_raises_conflict():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=type("Result", (), {"scalar_one_or_none": lambda self: object()})())
    with pytest.raises(ConflictError) as exc_info:
        await portal_account_service._check_portal_uniqueness(
            db,
            "tenant-001",
            EntityType.CUSTOMER.value,
            "https://portal.example.com/srm",
            "buyer@example.com",
        )
    assert exc_info.value.message_key == "errors.autotask.portal_account.duplicate"


def test_list_portal_accounts_api_returns_paginated_shape():
    client = TestClient(app)
    page = PortalListPageResponse(
        items=[PortalAccountResponse.model_validate(_portal_account(), from_attributes=True)],
        total=1,
        page=1,
        page_size=20,
    )

    async def override_user():
        return _user()

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides.clear()
    from app.core.deps import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    with patch(
        "app.api.portal_accounts.portal_account_service.list_portal_accounts",
        new=AsyncMock(return_value=page),
    ):
        response = client.get(
            "/api/v1/autotask/portal-accounts?page=1&pageSize=20",
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 1
    assert body["data"]["pageSize"] == 20
    assert body["data"]["items"][0]["portalUrl"] == "https://portal.example.com/srm"


def test_create_portal_account_api_requires_manage_access():
    client = TestClient(app)

    async def override_user():
        return _user(org_role="member")

    async def override_db():
        yield AsyncMock()

    from app.core.deps import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    response = client.post(
        "/api/v1/autotask/portal-accounts",
        headers={"Authorization": "Bearer test-token"},
        json={
            "entityType": "CUSTOMER",
            "erpEntityCode": "CUST-010",
            "erpEntityName": "新客户",
            "portalName": "新客户 SRM",
            "portalUrl": "https://portal.example.com/new",
            "loginAccount": "new@example.com",
            "clientOpenMode": "webcontents",
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["message_key"] == "errors.autotask.permission_denied"


def test_test_open_api_returns_open_context():
    client = TestClient(app)
    open_context = PortalTestOpenResponse(
        portal_account_id="portal-001",
        portal_name="客户 SRM 门户",
        portal_url="https://portal.example.com/srm",
        client_open_mode="webcontents",
        client_session_partition="persist:portal-001",
        status="ENABLED",
        allowed=True,
    )

    async def override_user():
        return _user()

    async def override_db():
        yield AsyncMock()

    from app.core.deps import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    with (
        patch(
            "app.api.portal_accounts.require_permission",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.api.portal_accounts.portal_account_service.test_open_portal_account",
            new=AsyncMock(return_value=open_context),
        ),
    ):
        response = client.post(
            "/api/v1/autotask/portal-accounts/portal-001/test-open",
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["allowed"] is True
    assert data["portalName"] == "客户 SRM 门户"
    assert data["clientSessionPartition"] == "persist:portal-001"


def test_test_open_api_returns_403_without_permission():
    client = TestClient(app)

    async def override_user():
        return _user()

    async def override_db():
        yield AsyncMock()

    from app.core.deps import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    with patch(
        "app.api.portal_accounts.require_permission",
        new=AsyncMock(side_effect=ForbiddenError(message_key="errors.autotask.permission_denied")),
    ):
        response = client.post(
            "/api/v1/autotask/portal-accounts/portal-001/test-open",
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["message_key"] == "errors.autotask.permission_denied"
