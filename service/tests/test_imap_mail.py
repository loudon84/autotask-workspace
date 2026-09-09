from datetime import UTC, datetime
from email.message import EmailMessage

from app.domain.mail_message import MailMessage
from app.integrations.imap_mail import ImapMailConnector


class FakeImap:
    def __init__(self) -> None:
        self.selected = None

    def select(self, folder, readonly=True):  # noqa: ANN001
        self.selected = (folder, readonly)
        return "OK", [b"2"]

    def uid(self, command, *args):  # noqa: ANN001
        if command == "SEARCH":
            return "OK", [b"10 12"]
        if command == "FETCH":
            msg = EmailMessage()
            msg["From"] = "noreply@boe.com"
            msg["To"] = "aa@example.com"
            msg["Date"] = "Tue, 8 Sep 2026 07:00:10 +0800"
            msg["Subject"] = "验证码"
            msg.set_content("您的验证码是 847291，5分钟内有效。")
            raw = msg.as_bytes()
            return "OK", [(b"12 (RFC822 {n})", raw)]
        raise AssertionError(command)

    def login(self, *_args):
        return "OK", []

    def logout(self):
        return "BYE", []


def test_connector_max_uid_and_fetch_since(monkeypatch):
    fake = FakeImap()
    connector = ImapMailConnector(
        host="imap.example.com",
        port=993,
        user="sys@example.com",
        auth="x",
        folder="BOE-SRM一站式平台-验证码",
        client=fake,
    )
    connector.connect()
    assert connector.max_uid() == 12
    messages = connector.fetch_since_uid(10)
    assert len(messages) == 1
    mail: MailMessage = messages[0]
    assert mail.uid == 12
    assert "aa@example.com" in mail.to_addrs
    assert "847291" in mail.text_body
    assert mail.sent_at.tzinfo is not None or mail.sent_at == datetime(2026, 9, 8, 7, 0, 10, tzinfo=UTC)
