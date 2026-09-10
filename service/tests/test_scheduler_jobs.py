"""Binding 不再写入 scheduler_jobs；旧 parse 工具仍可解析历史 JSON。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import BindingStatus
from app.services.binding_schedule import build_job_name, parse_schedule


def test_build_job_name():
    assert build_job_name("天地伟业", "客户订单", "扫单") == "天地伟业-客户订单-扫单"


def test_parse_schedule_missing_returns_none():
    assert parse_schedule({}) is None
    assert parse_schedule({"searches": []}) is None


def test_parse_schedule_valid():
    decl = parse_schedule(
        {
            "schedule": {
                "enabled": True,
                "cron": "0 8 * * *",
                "processName": "客户订单",
                "actionName": "扫单",
            }
        }
    )
    assert decl is not None
    assert decl.cron == "0 8 * * *"
    assert decl.process_name == "客户订单"
    assert decl.action_name == "扫单"


@pytest.mark.asyncio
async def test_enable_binding_does_not_touch_scheduler_jobs(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import workflow_binding_service as binding_svc

    binding = SimpleNamespace(
        id="b1",
        portal_account_id="p1",
        status=BindingStatus.DISABLED,
        config="{}",
    )
    monkeypatch.setattr(binding_svc, "get_workflow_binding", AsyncMock(return_value=binding))
    monkeypatch.setattr(binding_svc, "validate_successor_binding_config", AsyncMock())
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    await binding_svc.enable_workflow_binding(db, "tenant-1", "b1")
    assert binding.status == BindingStatus.ENABLED
    assert not hasattr(binding_svc, "scheduler_job_svc")


def test_lifespan_does_not_start_job_scheduler():
    import inspect

    from app import main

    source = inspect.getsource(main.lifespan)
    assert "JobScheduler" not in source
    assert "TimerScheduler" in source
