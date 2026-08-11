import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")

from fastapi.testclient import TestClient

from app.main import app


def test_root_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
