"""Normalized inbound mail. Connectors fill this; scenes consume it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MailMessage:
    uid: int
    to_addrs: tuple[str, ...]
    sent_at: datetime
    text_body: str
    folder: str = ""
    subject: str = ""
    from_addr: str = ""
