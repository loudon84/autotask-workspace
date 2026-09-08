"""京东方定时器入口：到点调用既有业务函数（不连库）。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import boe_timers


def _session_with_tenants(tenants: list[str]) -> tuple[type, MagicMock]:
    """构造 async_session_factory 替代品：execute 返回给定租户列表。"""
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

    await boe_timers.pack_match_due()

    assert match.await_count == 2
    assert match.await_args_list[0].kwargs["actor"] == "timer:boe.pack_match"


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
async def test_srm_login_due_collects_targets_without_rpa(
    monkeypatch: pytest.MonkeyPatch,
):
    from types import SimpleNamespace

    portals = [
        SimpleNamespace(
            id="p1",
            tenant_id="t1",
            category="BOE",
            status="ENABLED",
            login_account="V1002012AA",
            extra={"email": "aa@example.com"},
        ),
        SimpleNamespace(
            id="p2",
            tenant_id="t1",
            category="BOE",
            status="ENABLED",
            login_account="V1002012AA",
            extra={"email": "aa@example.com"},
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
    await boe_timers.srm_login_due()
    db.execute.assert_awaited()
