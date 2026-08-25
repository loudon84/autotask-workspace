"""验证用户缓存同步的网络边界。"""

import pytest

from app.services import user_sync


@pytest.mark.asyncio
async def test_fetch_user_from_backend_ignores_process_proxy(monkeypatch):
    init_options: dict[str, object] = {}

    class StubResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"data": {"id": "local-user"}}

    class StubClient:
        def __init__(self, **kwargs):
            init_options.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, headers):
            return StubResponse()

    monkeypatch.setattr(user_sync.httpx, "AsyncClient", StubClient)

    result = await user_sync._fetch_user_from_backend("local-token")

    assert result == {"id": "local-user"}
    assert init_options["timeout"] == 10.0
    assert init_options["trust_env"] is False


@pytest.mark.asyncio
async def test_fetch_subordinates_parses_auth_envelope(monkeypatch):
    class StubResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "code": 0,
                "data": [
                    {
                        "id": "a26a7cc6-5f48-4824-b554-bf48b51a7867",
                        "name": "张站",
                        "email": "zhangzhan@example.com",
                        "username": "smc-sz-hr15563",
                    }
                ],
            }

    class StubClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, headers):
            assert url.endswith("/api/v1/members/leader-1/subordinate")
            return StubResponse()

    monkeypatch.setattr(user_sync.httpx, "AsyncClient", StubClient)
    people = await user_sync.fetch_subordinates("token", "leader-1")
    assert people == [
        {
            "user_id": "a26a7cc6-5f48-4824-b554-bf48b51a7867",
            "name": "张站",
            "username": "smc-sz-hr15563",
        }
    ]


def test_parse_auth_people_keeps_name_and_job_number_apart():
    people = user_sync._parse_auth_people(
        {
            "data": [
                {
                    "id": "u1",
                    "name": "张站",
                    "username": "smc-sz-hr15563",
                }
            ]
        }
    )
    assert people == [
        {
            "user_id": "u1",
            "name": "张站",
            "username": "smc-sz-hr15563",
        }
    ]


def test_parse_org_member_info_uses_user_id_and_user_name():
    people = user_sync._parse_auth_people(
        {
            "data": [
                {
                    "id": "membership-1",
                    "user_id": "user-2",
                    "user_name": "张站",
                    "username": "smc-sz-hr15563",
                    "employee_no": "smc-sz-hr15563",
                }
            ]
        }
    )
    assert people == [
        {
            "user_id": "user-2",
            "name": "张站",
            "username": "smc-sz-hr15563",
        }
    ]


@pytest.mark.asyncio
async def test_load_managed_user_ids_uses_subordinate_api(monkeypatch):
    async def _subs(_token, _user_id):
        return [{"user_id": "user-2", "name": "张站", "username": "sz"}]

    monkeypatch.setattr(user_sync, "fetch_subordinates", _subs)
    ids = await user_sync._load_managed_user_ids(
        "token",
        "leader-1",
        {"is_super_admin": False, "is_task_admin": False},
    )
    assert ids == ["user-2"]


@pytest.mark.asyncio
async def test_load_managed_user_ids_caches_subordinates_for_task_admin(monkeypatch):
    async def _subs(_token, _user_id):
        return [{"user_id": "user-2", "name": "张站", "username": "sz"}]

    monkeypatch.setattr(user_sync, "fetch_subordinates", _subs)
    ids = await user_sync._load_managed_user_ids(
        "token",
        "admin-1",
        {"is_super_admin": False, "is_task_admin": True},
    )
    assert ids == ["user-2"]


def test_upsert_stores_task_admin_flag():
    entity = user_sync._upsert_user_cache(
        None,
        {
            "id": "admin-1",
            "name": "运维",
            "is_task_admin": True,
            "is_super_admin": False,
        },
        [],
    )
    assert entity.is_task_admin is True
    assert entity.is_super_admin is False
    assert entity.managed_user_ids == "[]"
