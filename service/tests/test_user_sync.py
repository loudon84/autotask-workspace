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
