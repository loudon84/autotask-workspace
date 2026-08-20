import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app
from app.models.user_cache import UserCache
from app.services.runtime_endpoints import (
    client_integration_endpoints,
    integration_lease_config,
    sdms_check_url,
)


def _user() -> UserCache:
    return UserCache(
        user_id="user-001",
        name="测试用户",
        email="user@example.com",
        current_org_id="tenant-001",
        org_role="admin",
        portal_org_role=None,
        is_super_admin=False,
        synced_at=datetime.now(UTC),
    )


def test_client_integration_endpoints_exposes_sdms_web_only(monkeypatch):
    monkeypatch.setattr("app.services.runtime_endpoints.settings.SDMS_BASE_URL", "http://sdms.example/")
    monkeypatch.setattr(
        "app.services.runtime_endpoints.settings.SMC_API_BASE_URL",
        "http://api.example",
    )
    monkeypatch.setattr("app.services.runtime_endpoints.settings.ERP_CLIENT_SECRET", "secret")
    payload = client_integration_endpoints()
    assert payload == {"sdmsBaseUrl": "http://sdms.example"}
    assert "erpClientSecret" not in payload
    assert "api.example" not in payload.values()


def test_sdms_check_url_uses_smc_api_not_sdms_web(monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime_endpoints.settings.SMC_API_BASE_URL",
        "http://api.qywx.example/",
    )
    monkeypatch.setattr(
        "app.services.runtime_endpoints.settings.SDMS_BASE_URL",
        "http://192.168.99.35:8080",
    )
    assert sdms_check_url() == "http://api.qywx.example/sdms/ar_check/view_doc_srm"


def test_lease_config_keeps_secrets_off_the_client_endpoint(monkeypatch):
    monkeypatch.setattr("app.services.runtime_endpoints.settings.SDMS_BASE_URL", "http://sdms.example")
    monkeypatch.setattr("app.services.runtime_endpoints.settings.ERP_BASE_URL", "http://erp.example")
    monkeypatch.setattr("app.services.runtime_endpoints.settings.ERP_CLIENT_ID", "smc_erp")
    monkeypatch.setattr("app.services.runtime_endpoints.settings.ERP_CLIENT_SECRET", "secret")
    lease = integration_lease_config()
    client = client_integration_endpoints()
    assert lease["erpClientSecret"] == "secret"
    assert "erpClientSecret" not in client
    assert "erpBaseUrl" not in client


def test_integration_endpoints_api_returns_sdms_base_url(monkeypatch):
    monkeypatch.setattr("app.services.runtime_endpoints.settings.SDMS_BASE_URL", "http://sdms.example/")
    client = TestClient(app)

    async def override_user():
        return _user()

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides.clear()
    from app.core.deps import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    response = client.get(
        "/api/v1/autotask/integration-endpoints",
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["sdmsBaseUrl"] == "http://sdms.example"
    assert "erpClientSecret" not in body["data"]
