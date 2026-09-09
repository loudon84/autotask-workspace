"""Worker API: IMAP watermark and this-click OTP. IMAP stays on Task."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.exceptions import BadRequestError
from app.integrations.imap_mail import MailImapError
from app.schemas.common import ApiResponse
from app.schemas.mail_otp import (
    MailOtpFetchRequest,
    MailOtpFetchResponse,
    MailOtpWatermarkResponse,
)
from app.services import mail_otp_service

router = APIRouter()


@router.post("/mail/otp/watermark", response_model=ApiResponse[MailOtpWatermarkResponse])
async def mail_otp_watermark(db: AsyncSession = Depends(get_db)):
    _ = db
    try:
        uid = await mail_otp_service.folder_watermark()
    except MailImapError as exc:
        raise BadRequestError(message=str(exc), message_key="errors.autotask.mail_imap") from exc
    return ApiResponse(data=MailOtpWatermarkResponse(uid=uid))


@router.post("/mail/otp", response_model=ApiResponse[MailOtpFetchResponse])
async def mail_otp_fetch(
    body: MailOtpFetchRequest,
    db: AsyncSession = Depends(get_db),
):
    _ = db
    try:
        picked = await mail_otp_service.fetch_fresh_otp(
            recipient=body.recipient,
            requested_at=body.requested_at,
            uid_watermark=body.uid_watermark,
        )
    except MailImapError as exc:
        raise BadRequestError(message=str(exc), message_key="errors.autotask.mail_imap") from exc
    if picked is None:
        return ApiResponse(data=MailOtpFetchResponse(found=False))
    return ApiResponse(
        data=MailOtpFetchResponse(found=True, uid=picked.uid, code=picked.code)
    )
