"""Portal owner ACL: grants are ignored; managed people stay empty until Auth ships."""

from datetime import UTC, datetime

import pytest
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache
from app.services.permission_service import (
    check_portal_permission,
    extract_managed_user_ids,
    is_scope_admin,
    visible_owner_ids,
)


def _user(**overrides) -> UserCache:
    fields = {
        "user_id": "user-1",
        "name": "客服",
        "email": "cs@example.com",
        "current_org_id": "org-1",
        "org_role": "member",
        "portal_org_role": "member",
        "is_super_admin": False,
        "is_task_admin": False,
        "managed_user_ids": "[]",
        "synced_at": datetime.now(UTC),
    }
    fields.update(overrides)
    return UserCache(**fields)


def test_extract_managed_user_ids_empty_when_auth_has_not_shipped():
    assert extract_managed_user_ids({}) == []
    assert extract_managed_user_ids({"name": "张三"}) == []


def test_extract_managed_user_ids_accepts_subordinate_payload():
    assert extract_managed_user_ids(
        {
            "data": [
                {"id": "a26a7cc6-5f48-4824-b554-bf48b51a7867", "name": "张站"},
                {"id": "8468ef67-e4d6-4efd-bc41-ca5189449b09", "name": "苏宇威"},
            ]
        }
    ) == []
    assert extract_managed_user_ids(
        {
            "subordinates": [
                {"id": "a26a7cc6-5f48-4824-b554-bf48b51a7867", "name": "张站"},
            ]
        }
    ) == ["a26a7cc6-5f48-4824-b554-bf48b51a7867"]
    assert extract_managed_user_ids({"managed_users": [{"id": "a"}, {"userId": "b"}]}) == [
        "a",
        "b",
    ]
    assert extract_managed_user_ids({"managedUserIds": ["c"]}) == ["c"]


def test_scope_admin_is_super_admin_task_admin_or_portal_org_admin():
    assert is_scope_admin(_user(portal_org_role="admin")) is True
    assert is_scope_admin(_user(is_super_admin=True, portal_org_role="member")) is True
    assert is_scope_admin(_user(is_task_admin=True, portal_org_role="member")) is True
    assert is_scope_admin(_user(org_role="admin", portal_org_role="member")) is False


def test_visible_owner_ids_include_cached_subordinates():
    user = _user()
    assert visible_owner_ids(user) == {"user-1"}
    leader = _user(managed_user_ids='["user-2"]')
    assert visible_owner_ids(leader) == {"user-1", "user-2"}


class _PortalResult:
    def __init__(self, portal):
        self._portal = portal

    def scalar_one_or_none(self):
        return self._portal


class _Db:
    def __init__(self, portal):
        self.portal = portal

    async def execute(self, _query):
        return _PortalResult(self.portal)


@pytest.mark.asyncio
async def test_member_can_see_own_portal_not_others():
    portal = PortalAccount(
        id="p1",
        tenant_id="org-1",
        entity_type="CUSTOMER",
        erp_entity_code="C1",
        erp_entity_name="客户",
        portal_name="门户",
        portal_url="https://example.com",
        login_account="a",
        created_by="other",
        owner_user_id="user-1",
    )
    user = _user()
    db = _Db(portal)
    assert await check_portal_permission(db, user, "org-1", "p1", "PORTAL_VIEW") is True
    portal.owner_user_id = "someone-else"
    assert await check_portal_permission(db, user, "org-1", "p1", "PORTAL_VIEW") is False


@pytest.mark.asyncio
async def test_leader_can_see_subordinate_portal():
    portal = PortalAccount(
        id="p1",
        tenant_id="org-1",
        entity_type="CUSTOMER",
        erp_entity_code="C1",
        erp_entity_name="客户",
        portal_name="门户",
        portal_url="https://example.com",
        login_account="a",
        created_by="user-2",
        owner_user_id="user-2",
    )
    leader = _user(managed_user_ids='["user-2"]')
    assert await check_portal_permission(_Db(portal), leader, "org-1", "p1", "PORTAL_VIEW") is True


@pytest.mark.asyncio
async def test_task_admin_can_see_any_portal():
    portal = PortalAccount(
        id="p1",
        tenant_id="org-1",
        entity_type="CUSTOMER",
        erp_entity_code="C1",
        erp_entity_name="客户",
        portal_name="门户",
        portal_url="https://example.com",
        login_account="a",
        created_by="other",
        owner_user_id="someone-else",
    )
    admin = _user(is_task_admin=True)
    assert await check_portal_permission(_Db(portal), admin, "org-1", "p1", "PORTAL_VIEW") is True
