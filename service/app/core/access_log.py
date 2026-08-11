"""AutoTask API access logging."""

import json
import logging
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("autotask.access")


def _infer_response_shape(payload: Any) -> tuple[str, int | None]:
    if not isinstance(payload, dict):
        return "unknown", None
    data = payload.get("data")
    if data is None:
        return "null", None
    if isinstance(data, list):
        return "list", len(data)
    if isinstance(data, dict):
        if "stats" in data and "taskTypeDistribution" in data:
            return "dashboard_summary", None
        if "items" in data:
            items = data.get("items")
            count = len(items) if isinstance(items, list) else None
            return "paginated_list", count
        if "todayTotal" in data or "ready" in data:
            return "dashboard_summary_legacy", None
        if "id" in data and "taskType" in data:
            return "task_detail", None
        if "url" in data:
            return "artifact_download_url", None
        return "object", None
    return "unknown", None


class AutotaskAccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/autotask"):
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 500
        body_chunks: list[bytes] = []

        async def _send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    body_chunks.append(chunk)
            await send(message)

        await self.app(scope, receive, _send)

        duration_ms = int((time.perf_counter() - started) * 1000)
        method = scope.get("method", "GET")
        path = scope.get("path", "")
        shape = "unknown"
        count: int | None = None
        if body_chunks:
            try:
                payload = json.loads(b"".join(body_chunks).decode("utf-8"))
                shape, count = _infer_response_shape(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                shape = "non_json"

        if count is None:
            logger.info(
                "%s %s %s shape=%s duration=%sms",
                method,
                path,
                status_code,
                shape,
                duration_ms,
            )
        else:
            logger.info(
                "%s %s %s shape=%s count=%s duration=%sms",
                method,
                path,
                status_code,
                shape,
                count,
                duration_ms,
            )
