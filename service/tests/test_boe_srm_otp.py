from datetime import UTC, datetime, timedelta

from app.domain.boe_srm_otp import extract_otp_code, pick_fresh_otp
from app.domain.mail_message import MailMessage


def _msg(
    uid: int,
    to: str,
    sent_at: datetime,
    body: str = "您的验证码是 123456，5分钟内有效。",
) -> MailMessage:
    return MailMessage(uid=uid, to_addrs=(to,), sent_at=sent_at, text_body=body)


def test_extract_otp_prefers_label_then_last_six_digits():
    assert extract_otp_code("验证码：847291 请尽快填写") == "847291"
    assert extract_otp_code("订单 100001 验证码 654321") == "654321"
    assert extract_otp_code("no code here") is None


def test_pick_uses_mail_after_this_click_for_this_recipient():
    requested = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    now = requested + timedelta(seconds=20)
    aa = "aa@example.com"
    ad = "ad@example.com"
    picked = pick_fresh_otp(
        [
            _msg(10, aa, requested - timedelta(minutes=2), "验证码 111111"),
            _msg(11, ad, now, "验证码 222222"),
            _msg(12, f"客服 <{aa}>", now, "验证码 333333"),
        ],
        recipient=aa,
        requested_at=requested,
        now=now,
        uid_watermark=10,
    )
    assert picked is not None
    assert picked.code == "333333"
    assert picked.uid == 12
    assert picked.recipient == aa


def test_pick_rejects_uid_already_seen_before_click():
    requested = datetime(2026, 9, 8, 7, 3, tzinfo=UTC)
    now = requested + timedelta(seconds=10)
    picked = pick_fresh_otp(
        [_msg(20, "aa@example.com", now, "验证码 111111")],
        recipient="aa@example.com",
        requested_at=requested,
        now=now,
        uid_watermark=20,
    )
    assert picked is None


def test_pick_rejects_historical_even_inside_five_minutes():
    requested = datetime(2026, 9, 8, 7, 3, tzinfo=UTC)
    older = requested - timedelta(minutes=3)
    now = requested + timedelta(seconds=10)
    picked = pick_fresh_otp(
        [_msg(21, "aa@example.com", older, "验证码 111111")],
        recipient="aa@example.com",
        requested_at=requested,
        now=now,
        uid_watermark=20,
    )
    assert picked is None


def test_pick_rejects_other_account_new_mail():
    requested = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    now = requested + timedelta(seconds=15)
    picked = pick_fresh_otp(
        [_msg(30, "ad@example.com", now, "验证码 444444")],
        recipient="aa@example.com",
        requested_at=requested,
        now=now,
        uid_watermark=29,
    )
    assert picked is None


def test_pick_rejects_code_older_than_five_minutes():
    requested = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    sent = requested + timedelta(seconds=5)
    now = sent + timedelta(minutes=5, seconds=1)
    picked = pick_fresh_otp(
        [_msg(40, "aa@example.com", sent, "验证码 555555")],
        recipient="aa@example.com",
        requested_at=requested,
        now=now,
        uid_watermark=39,
    )
    assert picked is None


def test_pick_newest_uid_when_two_fresh_codes():
    requested = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    first = requested + timedelta(seconds=8)
    second = requested + timedelta(seconds=12)
    now = requested + timedelta(seconds=20)
    picked = pick_fresh_otp(
        [
            _msg(50, "aa@example.com", first, "验证码 666666"),
            _msg(51, "aa@example.com", second, "验证码 777777"),
        ],
        recipient="AA@example.com",
        requested_at=requested,
        now=now,
        uid_watermark=49,
    )
    assert picked is not None
    assert picked.code == "777777"
    assert picked.uid == 51
