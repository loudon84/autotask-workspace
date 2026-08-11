"""RPA Engine HTTP 客户端测试。"""

from typing import Any

import pytest

from app.services import rpa_engine_client


@pytest.mark.asyncio
async def test_validate_binding_ignores_system_proxy(monkeypatch) -> None:
    init_options: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "valid": True,
                "rpaFlowVersionId": "flow-version-1",
                "checksum": "sha256:" + "a" * 64,
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs: Any) -> None:
            init_options.update(kwargs)

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        rpa_engine_client.settings,
        "RPA_ENGINE_VALIDATE_BINDING",
        True,
    )
    monkeypatch.setattr(
        rpa_engine_client.settings,
        "RPA_ENGINE_BASE_URL",
        "http://127.0.0.1:4610",
    )
    monkeypatch.setattr(
        rpa_engine_client.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    result = await rpa_engine_client.validate_binding(
        rpa_flow_id="flow-1",
        rpa_flow_version="1.0.0",
        workflow_code="workflow-1",
        actor_id="actor-1",
    )

    assert init_options["trust_env"] is False
    assert result == {
        "valid": True,
        "rpaFlowVersionId": "flow-version-1",
        "checksum": "a" * 64,
    }
