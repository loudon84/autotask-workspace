"""API cache-control middleware."""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class NoCacheAPIMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                ct = headers.get("content-type", "")
                if "text/event-stream" in ct:
                    headers["X-Accel-Buffering"] = "no"
                    headers["Cache-Control"] = "no-cache"
                elif "cache-control" not in headers:
                    headers.append("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, _send)
