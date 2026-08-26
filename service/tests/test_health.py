import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")

from fastapi.testclient import TestClient

from app.main import app


def test_root_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["pid"], int)
    assert payload["pid"] > 0
    assert payload["startedAt"]


def test_session_sync_requires_auth():
    client = TestClient(app)
    response = client.post("/api/v1/autotask/session/sync")
    assert response.status_code == 401
