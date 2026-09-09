"""Task-side OTP fetch: IMAP + pick_fresh_otp. Never logs the code."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.core.config import settings
from app.domain.boe_srm_otp import FreshOtp, pick_fresh_otp
from app.integrations.imap_mail import ImapMailConnector, MailImapError

logger = logging.getLogger(__name__)

# @lat: [[design-decisions#OTP Matches This Click]]


def _run_connector(fn_name: str, *args: object):
    with ImapMailConnector.from_settings() as connector:
        return getattr(connector, fn_name)(*args)


async def assert_imap_ready() -> int:
    """Handshake only. Failure means the whole login wave must not click 获取验证码."""
    try:
        watermark = await asyncio.to_thread(_run_connector, "max_uid")
    except MailImapError:
        raise
    except Exception as exc:
        raise MailImapError("IMAP 读取失败") from exc
    logger.info("IMAP ready folder_max_uid=%s", watermark)
    return int(watermark or 0)


async def folder_watermark() -> int:
    return await assert_imap_ready()


async def fetch_fresh_otp(
    *,
    recipient: str,
    requested_at: datetime,
    uid_watermark: int,
    now: datetime | None = None,
) -> FreshOtp | None:
    mailbox = (recipient or "").strip()
    if not mailbox:
        return None
    try:
        messages = await asyncio.to_thread(
            _run_connector, "fetch_since_uid", int(uid_watermark)
        )
    except MailImapError:
        raise
    picked = pick_fresh_otp(
        messages,
        recipient=mailbox,
        requested_at=requested_at,
        now=now or datetime.now(requested_at.tzinfo),
        uid_watermark=int(uid_watermark),
    )
    if picked is None:
        logger.info("OTP not found yet recipient_set=1 watermark=%s", uid_watermark)
        return None
    logger.info("OTP picked uid=%s (code redacted)", picked.uid)
    return picked


def otp_poll_seconds() -> float:
    return float(settings.ALI_MAIL_OTP_POLL_SECONDS)


def otp_wait_seconds() -> float:
    return float(settings.ALI_MAIL_OTP_WAIT_SECONDS)
