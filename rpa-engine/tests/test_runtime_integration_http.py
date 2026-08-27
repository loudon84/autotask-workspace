from __future__ import annotations

import json
import sys
import types

import httpx
import pytest

# IntegrationHttp 不依赖浏览器。本文件在 import runtime 之前挡住 Playwright，
# 避免本机 Engine 占用 greenlet.pyd 导致收集失败。
if "playwright.async_api" not in sys.modules:
    _playwright = types.ModuleType("playwright")
    _playwright.__path__ = []  # type: ignore[attr-defined]
    _async_api = types.ModuleType("playwright.async_api")

    class _PlaywrightError(Exception):
        pass

    class _PlaywrightTimeoutError(Exception):
        pass

    _async_api.Error = _PlaywrightError
    _async_api.TimeoutError = _PlaywrightTimeoutError
    sys.modules["playwright"] = _playwright
    sys.modules["playwright.async_api"] = _async_api

from nodeskclaw_rpa_engine.core.config import Settings
from nodeskclaw_rpa_engine.runtime.context import IntegrationHttp, TaskIntegrationCallSink
from nodeskclaw_rpa_engine.workers.task_client import TaskWorkerApiClient


def _worker_ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"code": 0, "data": None})


async def test_integration_http_posts_worker_api_without_access_token() -> None:
    worker_posts: list[tuple[str, dict[str, object]]] = []

    def worker_handler(request: httpx.Request) -> httpx.Response:
        worker_posts.append((request.url.path, json.loads(request.content)))
        return _worker_ok(request)

    def erp_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "secret-token-xyz",
                "token_type": "bearer",
                "expires_in": 3600,
            },
        )

    task_client = TaskWorkerApiClient(
        Settings(_env_file=None, app_env="test", task_api_base_url="http://task/api"),
        transport=httpx.MockTransport(worker_handler),
    )
    sink = TaskIntegrationCallSink(task_client, "run-runtime-1")
    http = IntegrationHttp(sink=sink, transport=httpx.MockTransport(erp_handler))
    try:
        response = await http.post(
            "https://erp.example.com/oauth/token",
            system="ERP",
            json={"client_secret": "cs-plain", "grant_type": "client_credentials"},
        )
        assert response.status_code == 200
    finally:
        await http.aclose()
        await task_client.close()

    assert len(worker_posts) == 1
    path, posted = worker_posts[0]
    assert path.endswith("/worker-api/runs/run-runtime-1/integration-calls")
    body = json.dumps(posted)
    assert "secret-token-xyz" not in body
    assert "cs-plain" not in body
    assert posted["system"] == "ERP"
    assert posted["method"] == "POST"
    assert posted["status_code"] == 200
    assert posted["url"] == "https://erp.example.com/oauth/token"


async def test_integration_http_timeout_still_posts_without_status_code() -> None:
    worker_posts: list[dict[str, object]] = []

    def worker_handler(request: httpx.Request) -> httpx.Response:
        worker_posts.append(json.loads(request.content))
        return _worker_ok(request)

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    task_client = TaskWorkerApiClient(
        Settings(_env_file=None, app_env="test", task_api_base_url="http://task/api"),
        transport=httpx.MockTransport(worker_handler),
    )
    sink = TaskIntegrationCallSink(task_client, "run-runtime-1")
    http = IntegrationHttp(sink=sink, transport=httpx.MockTransport(timeout_handler))
    try:
        with pytest.raises(httpx.TimeoutException):
            await http.get("https://erp.example.com/slow", system="ERP")
    finally:
        await http.aclose()
        await task_client.close()

    assert len(worker_posts) == 1
    posted = worker_posts[0]
    assert posted.get("status_code") is None
    assert posted["error_code"] == "TIMEOUT"
    assert posted["method"] == "GET"
