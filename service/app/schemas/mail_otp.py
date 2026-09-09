from datetime import datetime

from pydantic import AliasChoices, Field

from app.schemas.common import CamelModel


class MailOtpFetchRequest(CamelModel):
    recipient: str
    requested_at: datetime = Field(
        validation_alias=AliasChoices("requestedAt", "requested_at"),
        serialization_alias="requestedAt",
    )
    uid_watermark: int = Field(
        validation_alias=AliasChoices("uidWatermark", "uid_watermark"),
        serialization_alias="uidWatermark",
    )


class MailOtpWatermarkResponse(CamelModel):
    uid: int


class MailOtpFetchResponse(CamelModel):
    found: bool
    uid: int | None = None
    code: str | None = None
