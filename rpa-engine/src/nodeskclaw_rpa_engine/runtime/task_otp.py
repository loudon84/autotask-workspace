"""Task Worker API wrapper for BOE OTP. Never logs the code."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class OtpClient(Protocol):
    async def watermark(self) -> int: ...

    async def fetch_code(
        self, *, requested_at: datetime, uid_watermark: int
    ) -> str | None: ...


class TaskOtpClient:
    def __init__(self, client: Any, mailbox: str) -> None:
        self._client = client
        self._mailbox = mailbox

    async def watermark(self) -> int:
        data = await self._client.mail_otp_watermark()
        if not isinstance(data, dict):
            return 0
        return int(data.get("uid") or 0)

    async def fetch_code(
        self, *, requested_at: datetime, uid_watermark: int
    ) -> str | None:
        data = await self._client.mail_otp_fetch(
            recipient=self._mailbox,
            requested_at=requested_at,
            uid_watermark=uid_watermark,
        )
        if not isinstance(data, dict) or not data.get("found"):
            return None
        code = str(data.get("code") or "").strip()
        return code or None
