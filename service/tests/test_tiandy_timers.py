"""天地伟业定时器入口：到点调用既有业务函数（不连库）。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import tiandy_timers


@pytest.mark.asyncio
async def test_scan_pending_due_calls_run_scan_once(monkeypatch: pytest.MonkeyPatch):
    run_scan = AsyncMock(return_value=2)
    monkeypatch.setattr(tiandy_timers, "run_scan_once", run_scan)

    await tiandy_timers.scan_pending_due()

    run_scan.assert_awaited_once()
    assert run_scan.await_args.kwargs["actor"] == "timer:tiandy.scan_pending"


@pytest.mark.asyncio
async def test_sign_poll_due_calls_run_sign_poll_once(monkeypatch: pytest.MonkeyPatch):
    run_poll = AsyncMock(return_value={"candidate_count": 3, "created_count": 1})
    monkeypatch.setattr(
        tiandy_timers.process_svc, "run_sign_poll_once", run_poll
    )

    class _Session:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(
        tiandy_timers, "async_session_factory", lambda: _Session()
    )

    await tiandy_timers.sign_poll_due()

    run_poll.assert_awaited_once()
    assert run_poll.await_args.kwargs["actor"] == "timer:tiandy.sign_poll"
