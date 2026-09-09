from datetime import UTC, datetime

import pytest

from app.domain.boe_srm_otp import FreshOtp
from app.domain.mail_message import MailMessage
from app.services import mail_otp_service


@pytest.mark.asyncio
async def test_fetch_fresh_otp_uses_picker(monkeypatch: pytest.MonkeyPatch):
    requested = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    now = requested.replace(second=20)
    message = MailMessage(
        uid=12,
        to_addrs=("aa@example.com",),
        sent_at=now,
        text_body="验证码 111111",
        folder="otp",
    )

    def _run_connector(fn_name: str, *args: object):
        if fn_name == "fetch_since_uid":
            return [message]
        raise AssertionError(fn_name)

    monkeypatch.setattr(mail_otp_service, "_run_connector", _run_connector)
    picked = await mail_otp_service.fetch_fresh_otp(
        recipient="aa@example.com",
        requested_at=requested,
        uid_watermark=10,
        now=now,
    )
    assert isinstance(picked, FreshOtp)
    assert picked.uid == 12
    assert picked.code == "111111"
