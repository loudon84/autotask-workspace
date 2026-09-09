"""IMAP connector: connect, select folder, list MailMessage. Knows nothing about OTP."""

from __future__ import annotations

import email
import imaplib
import logging
import re
from datetime import UTC, datetime
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

from app.core.config import settings
from app.domain.mail_message import MailMessage
from app.integrations.imap_utf7 import encode_modified_utf7

logger = logging.getLogger(__name__)

# @lat: [[design-decisions#Mail Reader Is Scene-Based]]


class MailImapError(RuntimeError):
    """IMAP 连不上或选文件夹失败。不要因此去点获取验证码。"""


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for text, charset in decode_header(value):
        if isinstance(text, bytes):
            parts.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts)


def _body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                raw = part.get_payload(decode=True)
                if raw:
                    return raw.decode(part.get_content_charset() or "utf-8", errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                raw = part.get_payload(decode=True)
                if raw:
                    html = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
                    return re.sub(r"<[^>]+>", " ", html)
    raw = msg.get_payload(decode=True)
    if raw:
        return raw.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return ""


def _to_addrs(msg: email.message.Message) -> tuple[str, ...]:
    found: list[str] = []
    for header in msg.get_all("To", []):
        decoded = _decode_header(str(header))
        for part in decoded.split(","):
            _, addr = parseaddr(part)
            mailbox = (addr or part).strip()
            if mailbox:
                found.append(mailbox)
    return tuple(found)


def _sent_at(msg: email.message.Message) -> datetime:
    raw = msg.get("Date")
    if raw:
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except (TypeError, ValueError, OverflowError):
            pass
    return datetime.now(UTC)


class ImapMailConnector:
    """Only connectivity and fetch. Folder name is an argument, not OTP knowledge."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        auth: str,
        folder: str,
        readonly: bool = True,
        client: Any | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.auth = auth
        self.folder = folder
        self.readonly = readonly
        self._client = client
        self._owns_client = client is None

    @classmethod
    def from_settings(cls) -> ImapMailConnector:
        user = str(settings.ALI_MAIL_USER or "").strip()
        auth = str(settings.ALI_MAIL_AUTH or "").strip()
        if not user or not auth:
            raise MailImapError("未配置系统邮箱 IMAP（ALI_MAIL_USER / ALI_MAIL_AUTH）")
        return cls(
            host=str(settings.ALI_MAIL_HOST or "imap.qiye.aliyun.com").strip(),
            port=int(settings.ALI_MAIL_PORT or 993),
            user=user,
            auth=auth,
            folder=str(settings.ALI_MAIL_FOLDER or "BOE-SRM一站式平台-验证码").strip(),
            readonly=bool(settings.ALI_MAIL_READONLY),
        )

    def __enter__(self) -> ImapMailConnector:
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def connect(self) -> None:
        if self._client is None:
            try:
                self._client = imaplib.IMAP4_SSL(self.host, self.port)
            except OSError as exc:
                raise MailImapError(f"IMAP 连不上 {self.host}:{self.port}") from exc
            try:
                self._client.login(self.user, self.auth)
            except imaplib.IMAP4.error as exc:
                raise MailImapError("IMAP 登录失败") from exc
        folder = encode_modified_utf7(self.folder)
        status, data = self._client.select(folder, readonly=self.readonly)
        if status != "OK":
            raise MailImapError("IMAP 选文件夹失败")
        del data

    def close(self) -> None:
        if self._client is None or not self._owns_client:
            return
        try:
            self._client.logout()
        except Exception:
            logger.debug("IMAP logout failed", exc_info=True)
        self._client = None

    def max_uid(self) -> int:
        uids = self._search_uids()
        return max(uids) if uids else 0

    def fetch_since_uid(self, watermark: int) -> list[MailMessage]:
        messages: list[MailMessage] = []
        for uid in self._search_uids():
            if uid <= watermark:
                continue
            message = self._fetch_uid(uid)
            if message is not None:
                messages.append(message)
        return messages

    def _search_uids(self) -> list[int]:
        if self._client is None:
            raise MailImapError("IMAP 未连接")
        status, data = self._client.uid("SEARCH", None, "ALL")
        if status != "OK" or not data or data[0] is None:
            return []
        raw = data[0]
        text = raw.decode("ascii", errors="replace") if isinstance(raw, bytes) else str(raw)
        return [int(part) for part in text.split() if part.isdigit()]

    def _fetch_uid(self, uid: int) -> MailMessage | None:
        if self._client is None:
            raise MailImapError("IMAP 未连接")
        status, payload = self._client.uid("FETCH", str(uid), "(RFC822)")
        if status != "OK" or not payload:
            return None
        raw = None
        for item in payload:
            if isinstance(item, tuple) and len(item) >= 2:
                raw = item[1]
                break
        if not isinstance(raw, (bytes, bytearray)):
            return None
        msg = email.message_from_bytes(bytes(raw))
        _, from_addr = parseaddr(msg.get("From", ""))
        return MailMessage(
            uid=uid,
            to_addrs=_to_addrs(msg),
            sent_at=_sent_at(msg),
            text_body=_body_text(msg),
            folder=self.folder,
            subject=_decode_header(msg.get("Subject")),
            from_addr=from_addr,
        )
