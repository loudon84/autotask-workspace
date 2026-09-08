"""BOE SRM OTP scene: pick the code from THIS click, not leftover mail."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parseaddr

from app.domain.mail_message import MailMessage

# @lat: [[design-decisions#OTP Matches This Click]]

OTP_TTL = timedelta(minutes=5)
CLOCK_SKEW = timedelta(seconds=15)

_CODE_AFTER_LABEL = re.compile(r"验证码[^\d]{0,30}(\d{6})")
_ANY_SIX_DIGITS = re.compile(r"\b\d{6}\b")


@dataclass(frozen=True)
class FreshOtp:
    uid: int
    code: str
    sent_at: datetime
    recipient: str


def normalize_mailbox(value: str) -> str:
    _, addr = parseaddr((value or "").strip())
    return (addr or value or "").strip().lower()


def extract_otp_code(text: str) -> str | None:
    if not text:
        return None
    labeled = _CODE_AFTER_LABEL.search(text)
    if labeled:
        return labeled.group(1)
    all6 = _ANY_SIX_DIGITS.findall(text)
    return all6[-1] if all6 else None


def _recipients(message: MailMessage) -> set[str]:
    found: set[str] = set()
    for raw in message.to_addrs:
        mailbox = normalize_mailbox(raw)
        if mailbox:
            found.add(mailbox)
    return found


def pick_fresh_otp(
    messages: list[MailMessage] | tuple[MailMessage, ...],
    *,
    recipient: str,
    requested_at: datetime,
    now: datetime,
    uid_watermark: int,
    ttl: timedelta = OTP_TTL,
    clock_skew: timedelta = CLOCK_SKEW,
) -> FreshOtp | None:
    """Return the OTP created by this Get-Code click.

    Historical folder mail is ignored even if still inside the 5-minute window.
    Another account's mail is ignored even if it is newer.
    """
    wanted = normalize_mailbox(recipient)
    if not wanted:
        return None
    earliest = requested_at - clock_skew
    latest_age = now + clock_skew
    chosen: MailMessage | None = None
    chosen_code: str | None = None
    for message in messages:
        if message.uid <= uid_watermark:
            continue
        if wanted not in _recipients(message):
            continue
        sent_at = message.sent_at
        if sent_at < earliest:
            continue
        if sent_at > latest_age:
            continue
        if now - sent_at > ttl:
            continue
        code = extract_otp_code(message.text_body)
        if not code:
            continue
        if chosen is None or message.uid > chosen.uid:
            chosen = message
            chosen_code = code
    if chosen is None or chosen_code is None:
        return None
    return FreshOtp(
        uid=chosen.uid,
        code=chosen_code,
        sent_at=chosen.sent_at,
        recipient=wanted,
    )
