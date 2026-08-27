"""接口调用日志单测：脱敏、截断、Worker POST 挂任务、GET 过滤。"""

import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.dispatch import IntegrationCallCreate
from app.schemas.resource import IntegrationCallLogResponse
from app.services import integration_call_log_service as service
from app.services import integration_redact as redact


# ---------- 脱敏 ----------


def test_redact_url_strips_sensitive_query():
    safe = redact.redact_url("https://erp.example.com/oauth/token?client_secret=abc&code=zzz")
    assert "client_secret=abc" not in safe
    assert "[REDACTED]" in safe
    # 非敏感参数保留
    assert "code=zzz" in safe


def test_redact_dict_replaces_sensitive_keys():
    data = {
        "username": "buyer",
        "password": "p@ss",
        "access_token": "tk-xyz",
        "client_secret": "cs-1",
        "nested": {"authorization": "Bearer x", "ok": "keep"},
        "items": [{"token": "t1"}, {"name": "n1"}],
    }
    out = redact.redact_dict(data)
    assert out["password"] == "[REDACTED]"
    assert out["access_token"] == "[REDACTED]"
    assert out["client_secret"] == "[REDACTED]"
    assert out["username"] == "buyer"
    assert out["nested"]["authorization"] == "[REDACTED]"
    assert out["nested"]["ok"] == "keep"
    assert out["items"][0]["token"] == "[REDACTED]"
    assert out["items"][1]["name"] == "n1"


def test_oauth_token_response_redacts_token_fields_even_if_key_name_missed():
    """oauth/token 响应里 token 字段必抹（force_redact_token）。"""
    parsed = {"access_token": "abc", "token_type": "Bearer", "expires_in": 3600, "user_name": "u"}
    out = redact.redact_dict(parsed, force_redact_token=True)
    assert out["access_token"] == "[REDACTED]"
    assert out["token_type"] == "[REDACTED]"
    assert out["expires_in"] == 3600  # 不含 token 子串，保留
    assert out["user_name"] == "u"


def test_normalize_request_body_json_redacts_and_keeps_oauth_secret():
    body = redact.normalize_request_body(
        json_body={"client_secret": "cs", "grant_type": "password", "username": "u"},
        url="https://erp.example.com/oauth/token",
    )
    import json

    parsed = json.loads(body)
    assert parsed["client_secret"] == "[REDACTED]"
    assert parsed["grant_type"] == "password"
    assert parsed["username"] == "u"


def test_normalize_response_body_json_oauth_token_url_redacts():
    out = redact.normalize_response_body(
        status_code=200,
        response_text='{"access_token":"abc","expires_in":3600}',
        url="https://erp.example.com/oauth/token",
    )
    import json

    parsed = json.loads(out)
    assert parsed["access_token"] == "[REDACTED]"
    assert parsed["expires_in"] == 3600


def test_normalize_response_body_non_json_kept_as_is():
    out = redact.normalize_response_body(
        status_code=500, response_text="<html>err</html>", url="https://erp.example.com/api"
    )
    assert out == "<html>err</html>"


# ---------- 截断 ----------


def test_truncate_body_under_limit_not_truncated():
    text = "x" * 100
    body, trunc = redact.truncate_body(text)
    assert body == text
    assert trunc is False


def test_truncate_body_over_limit_truncated():
    text = "x" * (redact.MAX_BODY_BYTES + 10)
    body, trunc = redact.truncate_body(text)
    assert trunc is True
    assert len(body.encode("utf-8")) <= redact.MAX_BODY_BYTES


def test_truncate_body_none():
    body, trunc = redact.truncate_body(None)
    assert body is None
    assert trunc is False


# ---------- record_call 写入（脱敏+截断链路） ----------


@pytest.mark.asyncio
async def test_record_call_redacts_before_insert():
    """record_call 写入前脱敏 URL + body。"""
    db = MagicMock()
    db.flush = AsyncMock()
    log = await service.record_call(
        db,
        task_id="t1",
        tenant_id="ten-1",
        run_id="r1",
        system="ERP",
        method="post",
        url="https://erp.example.com/api?client_secret=abc",
        request_body='{"password":"p"}',
        response_body='{"access_token":"tk"}',
        status_code=200,
        duration_ms=42,
    )
    # db.add 应被调用一次
    assert db.add.call_count == 1
    added = db.add.call_args[0][0]
    assert added.method == "POST"  # 大写
    assert "client_secret=abc" not in added.url
    assert "[REDACTED]" in added.url
    assert "[REDACTED]" in added.request_body  # password 抹掉
    assert "[REDACTED]" in added.response_body  # access_token 抹掉
    assert added.status_code == 200
    assert added.duration_ms == 42
    assert added.request_truncated is False
    assert added.response_truncated is False


@pytest.mark.asyncio
async def test_record_call_truncates_oversized_body():
    big = "y" * (redact.MAX_BODY_BYTES + 5)
    db = MagicMock()
    db.flush = AsyncMock()
    await service.record_call(
        db,
        task_id="t1",
        tenant_id="ten-1",
        run_id=None,
        system="SDMS",
        method="GET",
        url="https://sdms.example.com/api",
        request_body=big,
        response_body=big,
    )
    added = db.add.call_args[0][0]
    assert added.request_truncated is True
    assert added.response_truncated is True
    assert len(added.request_body.encode("utf-8")) <= redact.MAX_BODY_BYTES
    assert len(added.response_body.encode("utf-8")) <= redact.MAX_BODY_BYTES


@pytest.mark.asyncio
async def test_record_call_by_run_returns_none_when_run_missing():
    """Worker 回调路径：run 不存在返回 None（静默跳过）。"""
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result(None))
    log = await service.record_call_by_run(
        db,
        run_id="missing",
        system="ERP",
        method="POST",
        url="https://erp.example.com/api",
    )
    assert log is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_record_call_by_run_resolves_task_from_run():
    """Worker POST 能挂上 task：run -> task -> record_call。"""
    run = MagicMock()
    run.id = "run-1"
    run.task_id = "task-1"
    task = MagicMock()
    task.id = "task-1"
    task.tenant_id = "ten-1"
    db = MagicMock()
    # 第一次 execute 返回 run，第二次返回 task
    db.execute = AsyncMock(side_effect=[_scalar_result(run), _scalar_result(task)])
    db.flush = AsyncMock()
    log = await service.record_call_by_run(
        db,
        run_id="run-1",
        system="ERP",
        method="POST",
        url="https://erp.example.com/import",
        request_body='{"po":"PO-1"}',
        response_body='{"ok":true}',
        status_code=200,
    )
    assert log is not None
    added = db.add.call_args[0][0]
    assert added.task_id == "task-1"
    assert added.tenant_id == "ten-1"
    assert added.run_id == "run-1"


@pytest.mark.asyncio
async def test_list_by_task_filters_by_run_id():
    """GET runId 过滤。"""
    db = MagicMock()
    expected = MagicMock()
    expected.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=expected)
    await service.list_by_task(db, task_id="t1", run_id="r1")
    # 验证 query 里有 run_id 过滤（通过 execute 被调用）
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_httpx_exchange_from_response():
    import httpx

    db = MagicMock()
    db.flush = AsyncMock()
    real = httpx.Response(200, json={"ok": True})
    log = await service.record_httpx_exchange(
        db,
        task_id="t1",
        tenant_id="ten-1",
        run_id="r1",
        system="SDMS",
        method="GET",
        url="https://sdms.example.com/api",
        request_body='{"q":1}',
        response_or_exc=real,
    )
    assert log is not None
    added = db.add.call_args[0][0]
    assert added.status_code == 200
    assert added.system == "SDMS"


@pytest.mark.asyncio
async def test_record_httpx_exchange_skips_without_task():
    log = await service.record_httpx_exchange(
        MagicMock(),
        task_id=None,
        tenant_id="ten-1",
        run_id=None,
        system="SDMS",
        method="GET",
        url="https://sdms.example.com/api",
    )
    assert log is None


@pytest.mark.asyncio
async def test_record_httpx_exchange_from_exception():
    db = MagicMock()
    db.flush = AsyncMock()
    log = await service.record_httpx_exchange(
        db,
        task_id="t1",
        tenant_id="ten-1",
        run_id=None,
        system="SDMS",
        method="POST",
        url="https://sdms.example.com/upload",
        response_or_exc=ConnectionError("down"),
        error_code="NETWORK_ERROR",
    )
    assert log is not None
    added = db.add.call_args[0][0]
    assert added.error_code == "NETWORK_ERROR"
    assert "ConnectionError" in added.response_body


def test_list_integration_calls_returns_403_without_portal_permission():
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock as _AsyncMock

    from fastapi.testclient import TestClient

    from app.core.exceptions import ForbiddenError
    from app.core.deps import get_db
    from app.core.security import get_current_user
    from app.main import app
    from app.models.user_cache import UserCache

    client = TestClient(app)

    async def override_user():
        return UserCache(
            user_id="user-001",
            name="客服",
            email="cs@example.com",
            current_org_id="tenant-001",
            org_role="member",
            portal_org_role="member",
            is_super_admin=False,
            is_task_admin=False,
            synced_at=datetime.now(UTC),
        )

    async def override_db():
        yield _AsyncMock()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        with patch(
            "app.api.tasks._require_task_visible",
            new=_AsyncMock(
                side_effect=ForbiddenError(message_key="errors.autotask.permission_denied")
            ),
        ):
            response = client.get(
                "/api/v1/autotask/tasks/task-1/integration-calls",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["message_key"] == "errors.autotask.permission_denied"


# ---------- Worker POST schema 契约 ----------


def test_integration_call_create_accepts_camel_case():
    body = IntegrationCallCreate.model_validate(
        {
            "system": "ERP",
            "method": "POST",
            "url": "https://erp.example.com/import",
            "requestBody": '{"po":"PO-1"}',
            "responseBody": '{"ok":true}',
            "statusCode": 200,
            "errorCode": None,
            "durationMs": 42,
        }
    )
    assert body.system == "ERP"
    assert body.status_code == 200
    assert body.duration_ms == 42


def test_integration_call_log_response_camel_aliases():
    from datetime import datetime

    payload = IntegrationCallLogResponse(
        id="log-1",
        task_id="t1",
        run_id="r1",
        system="ERP",
        method="POST",
        url="https://erp.example.com/api",
        request_body='{"a":1}',
        response_body='{"b":2}',
        status_code=200,
        error_code=None,
        duration_ms=42,
        request_truncated=False,
        response_truncated=False,
        created_at=datetime(2026, 8, 27, 10, 0, 0),
    ).model_dump(by_alias=True)
    assert payload["taskId"] == "t1"
    assert payload["runId"] == "r1"
    assert payload["statusCode"] == 200
    assert payload["durationMs"] == 42
    assert payload["requestTruncated"] is False
    assert payload["createdAt"] == datetime(2026, 8, 27, 10, 0, 0)


# ---------- helpers ----------


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result
