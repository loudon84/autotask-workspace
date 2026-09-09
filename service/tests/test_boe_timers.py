from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.imap_mail import MailImapError
from app.services import boe_timers
from app.services.timer_registry import TimerBusinessError


def _session_with_tenants(tenants: list[str]) -> tuple[type, MagicMock]:
    result = MagicMock()
    result.scalars.return_value.all.return_value = tenants
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.rollback = AsyncMock()

    class _Session:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return None

    return _Session, db


@pytest.mark.asyncio
async def test_pack_match_due_matches_each_tenant(monkeypatch: pytest.MonkeyPatch):
    match = AsyncMock(return_value={"created_count": 1})
    monkeypatch.setattr(
        boe_timers.boe_packing_service, "match_delivery_plans", match
    )
    session_factory, _db = _session_with_tenants(["tenant-1", "tenant-2"])
    monkeypatch.setattr(boe_timers, "async_session_factory", session_factory)

    summary = await boe_timers.pack_match_due()

    assert match.await_count == 2
    assert match.await_args_list[0].kwargs["actor"] == "timer:boe.pack_match"
    assert "新建 2 单" in summary


@pytest.mark.asyncio
async def test_pack_match_due_continues_after_tenant_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    match = AsyncMock(side_effect=[RuntimeError("网络失败"), {"created_count": 3}])
    monkeypatch.setattr(
        boe_timers.boe_packing_service, "match_delivery_plans", match
    )
    session_factory, db = _session_with_tenants(["tenant-1", "tenant-2"])
    monkeypatch.setattr(boe_timers, "async_session_factory", session_factory)

    await boe_timers.pack_match_due()

    assert match.await_count == 2
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_pack_match_due_no_tenant_no_match(monkeypatch: pytest.MonkeyPatch):
    match = AsyncMock()
    monkeypatch.setattr(
        boe_timers.boe_packing_service, "match_delivery_plans", match
    )
    session_factory, _db = _session_with_tenants([])
    monkeypatch.setattr(boe_timers, "async_session_factory", session_factory)

    await boe_timers.pack_match_due()

    match.assert_not_awaited()



@pytest.mark.asyncio
async def test_srm_login_due_fails_when_imap_down(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        boe_timers.mail_otp_service,
        "assert_imap_ready",
        AsyncMock(side_effect=MailImapError("IMAP 连不上 imap.example.com:993")),
    )
    with pytest.raises(TimerBusinessError, match="IMAP 连不上"):
        await boe_timers.srm_login_due()


@pytest.mark.asyncio
async def test_srm_login_due_serial_login_and_summary(monkeypatch: pytest.MonkeyPatch):
    portals = [
        SimpleNamespace(
            id="p1",
            tenant_id="t1",
            category="BOE",
            status="ENABLED",
            login_account="V1002012AA",
            extra={"email": "aa@example.com"},
            credential_ref="secret",
            entity_type="CUSTOMER",
            erp_entity_code="C1",
            erp_entity_name="A",
        ),
        SimpleNamespace(
            id="p2",
            tenant_id="t1",
            category="BOE",
            status="ENABLED",
            login_account="V1002012AA",
            extra={"email": "aa@example.com"},
            credential_ref="secret",
            entity_type="CUSTOMER",
            erp_entity_code="C2",
            erp_entity_name="B",
        ),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = portals
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    class _Session:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(boe_timers, "async_session_factory", _Session)
    monkeypatch.setattr(
        boe_timers.mail_otp_service, "assert_imap_ready", AsyncMock(return_value=9)
    )
    login = AsyncMock(return_value="成功")
    monkeypatch.setattr(boe_timers.login_svc, "login_one_account", login)
    summary = await boe_timers.srm_login_due()
    assert "V1002012AA 成功" in summary
    assert login.await_count == 1


@pytest.mark.asyncio
async def test_srm_login_due_missing_email_is_failure(monkeypatch: pytest.MonkeyPatch):
    portals = [
        SimpleNamespace(
            id="p1",
            tenant_id="t1",
            category="BOE",
            status="ENABLED",
            login_account="V1002012AD",
            extra={},
            credential_ref="secret",
            entity_type="CUSTOMER",
            erp_entity_code="C1",
            erp_entity_name="A",
        ),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = portals
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    class _Session:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(boe_timers, "async_session_factory", _Session)
    monkeypatch.setattr(
        boe_timers.mail_otp_service, "assert_imap_ready", AsyncMock(return_value=1)
    )
    with pytest.raises(TimerBusinessError, match="没有门户填写邮箱"):
        await boe_timers.srm_login_due()
