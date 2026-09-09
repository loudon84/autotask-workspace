"""Mail scene plugins. Connector never branches on folder == OTP."""

from __future__ import annotations

from typing import Protocol

from app.domain.mail_message import MailMessage

# @lat: [[design-decisions#Mail Reader Is Scene-Based]]


class MailScene(Protocol):
    code: str

    def match(self, message: MailMessage) -> bool: ...

    def parse(self, message: MailMessage) -> object: ...


class SalesOrderFromMailScene:
    """Reserved. Order-from-mail is a later design."""

    code = "sales_order_from_mail"

    def match(self, message: MailMessage) -> bool:
        del message
        return False

    def parse(self, message: MailMessage) -> object:
        del message
        raise NotImplementedError("sales_order_from_mail is not implemented")
