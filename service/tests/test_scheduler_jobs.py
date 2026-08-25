"""scheduler_jobs 插入规则与按门户开火（不连库）。"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import UnprocessableError
from app.models.enums import BindingStatus
from app.services import scheduler_job_service as job_svc
from app.services.binding_schedule import build_job_name, parse_schedule
from app.services.cron_schedule import seconds_until_due
from app.services.job_scheduler import JobScheduler
from app.services.process_instance_service import (
    CHECK_REPLY_TEMPLATE_CODE,
    SCAN_TASK_TYPE,
)


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


def test_invalid_schedule_rejects():
    with pytest.raises(UnprocessableError):
        parse_schedule(
            {
                "schedule": {
                    "cron": "not-a-cron",
                    "processName": "客户订单",
                    "actionName": "扫单",
                }
            }
        )
    with pytest.raises(UnprocessableError):
        parse_schedule({"schedule": {"cron": "0 8 * * *", "processName": "客户订单"}})


@pytest.mark.asyncio
async def test_first_save_with_schedule_inserts_job(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(job_svc, "get_job_by_binding_id", AsyncMock(return_value=None))
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    binding = SimpleNamespace(id="b1", status=BindingStatus.ENABLED)
    portal = SimpleNamespace(id="p1", portal_name="天地伟业")
    config = {
        "schedule": {
            "enabled": True,
            "cron": "0 8 * * *",
            "processName": "客户订单",
            "actionName": "扫单",
        }
    }
    job = await job_svc.sync_scheduler_job_from_binding(
        session, binding=binding, portal=portal, config=config
    )
    assert job is not None
    assert job.name == "天地伟业-客户订单-扫单"
    assert job.cron == "0 8 * * *"
    assert job.enabled is True
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_second_save_does_not_overwrite_cron(monkeypatch: pytest.MonkeyPatch):
    existing = SimpleNamespace(
        id="job-1",
        binding_id="b1",
        cron="0 8 * * *",
        name="天地伟业-客户订单-扫单",
        enabled=True,
    )
    monkeypatch.setattr(job_svc, "get_job_by_binding_id", AsyncMock(return_value=existing))
    session = MagicMock()
    session.add = MagicMock()
    binding = SimpleNamespace(id="b1", status=BindingStatus.ENABLED)
    portal = SimpleNamespace(id="p1", portal_name="天地伟业")
    config = {
        "schedule": {
            "enabled": False,
            "cron": "*/5 * * * *",
            "processName": "客户订单",
            "actionName": "扫单",
        }
    }
    job = await job_svc.sync_scheduler_job_from_binding(
        session, binding=binding, portal=portal, config=config
    )
    assert job is existing
    assert job.cron == "0 8 * * *"
    session.add.assert_not_called()

    job2 = await job_svc.sync_scheduler_job_from_binding(
        session, binding=binding, portal=portal, config={}
    )
    assert job2 is existing
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_schedule_rejects_without_insert(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(job_svc, "get_job_by_binding_id", AsyncMock(return_value=None))
    session = MagicMock()
    session.add = MagicMock()
    binding = SimpleNamespace(id="b1", status=BindingStatus.ENABLED)
    portal = SimpleNamespace(id="p1", portal_name="天地伟业")
    with pytest.raises(UnprocessableError):
        await job_svc.sync_scheduler_job_from_binding(
            session,
            binding=binding,
            portal=portal,
            config={
                "schedule": {
                    "cron": "99 * * * *",
                    "processName": "x",
                    "actionName": "y",
                }
            },
        )
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_disable_binding_disables_job(monkeypatch: pytest.MonkeyPatch):
    existing = SimpleNamespace(id="job-1", enabled=True)
    monkeypatch.setattr(job_svc, "get_job_by_binding_id", AsyncMock(return_value=existing))
    session = MagicMock()
    binding = SimpleNamespace(id="b1", status=BindingStatus.DISABLED)
    portal = SimpleNamespace(id="p1", portal_name="天地伟业")
    job = await job_svc.sync_scheduler_job_from_binding(
        session,
        binding=binding,
        portal=portal,
        config={
            "schedule": {
                "enabled": True,
                "cron": "0 8 * * *",
                "processName": "客户订单",
                "actionName": "扫单",
            }
        },
    )
    assert job.enabled is False


@pytest.mark.asyncio
async def test_enable_binding_does_not_reenable_job(monkeypatch: pytest.MonkeyPatch):
    from app.services import workflow_binding_service as binding_svc

    job = SimpleNamespace(enabled=False, binding_id="b1")
    binding = SimpleNamespace(
        id="b1",
        portal_account_id="p1",
        status=BindingStatus.DISABLED,
        config="{}",
    )
    monkeypatch.setattr(binding_svc, "get_workflow_binding", AsyncMock(return_value=binding))
    monkeypatch.setattr(binding_svc, "validate_successor_binding_config", AsyncMock())
    monkeypatch.setattr(
        binding_svc.scheduler_job_svc,
        "sync_scheduler_job_from_binding",
        AsyncMock(),
    )
    monkeypatch.setattr(
        binding_svc.scheduler_job_svc,
        "disable_job_for_binding",
        AsyncMock(),
    )
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    await binding_svc.enable_workflow_binding(db, "tenant-1", "b1")
    assert job.enabled is False
    assert binding.status == BindingStatus.ENABLED
    binding_svc.scheduler_job_svc.sync_scheduler_job_from_binding.assert_not_called()
    binding_svc.scheduler_job_svc.disable_job_for_binding.assert_not_called()


class _Scalar:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FireSession:
    def __init__(self, binding, template, portal):
        self._responses = [_Scalar(binding), _Scalar(template), _Scalar(portal)]

    async def execute(self, _stmt):
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_fire_scan_job_calls_create_scan_task(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    async def _create(_db, tenant_id, portal_account_id, *, actor):
        captured["tenant_id"] = tenant_id
        captured["portal_account_id"] = portal_account_id
        captured["actor"] = actor
        return SimpleNamespace(id="task-1")

    monkeypatch.setattr(job_svc, "create_scan_task", _create)
    job = SimpleNamespace(
        id="job-1",
        binding_id="b1",
        portal_account_id="portal-a",
        name="天地伟业-客户订单-扫单",
    )
    binding = SimpleNamespace(id="b1", workflow_template_id="tpl-1")
    template = SimpleNamespace(code=SCAN_TASK_TYPE)
    portal = SimpleNamespace(id="portal-a", tenant_id="tenant-1")
    await job_svc.fire_scheduler_job(_FireSession(binding, template, portal), job)
    assert captured == {
        "tenant_id": "tenant-1",
        "portal_account_id": "portal-a",
        "actor": "scheduler-job",
    }


@pytest.mark.asyncio
async def test_fire_sign_poll_job_passes_portal(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    async def _run(_db, *, actor, portal_account_id=None):
        captured["actor"] = actor
        captured["portal_account_id"] = portal_account_id
        return {"candidate_count": 1, "created_count": 1}

    monkeypatch.setattr(job_svc, "run_sign_poll_once", _run)
    job = SimpleNamespace(
        id="job-2",
        binding_id="b2",
        portal_account_id="portal-a",
        name="天地伟业-客户订单-回签轮询",
    )
    binding = SimpleNamespace(id="b2", workflow_template_id="tpl-2")
    template = SimpleNamespace(code=CHECK_REPLY_TEMPLATE_CODE)
    portal = SimpleNamespace(id="portal-a", tenant_id="tenant-1")
    await job_svc.fire_scheduler_job(_FireSession(binding, template, portal), job)
    assert captured["portal_account_id"] == "portal-a"
    assert captured["actor"] == "scheduler-job"


@pytest.mark.asyncio
async def test_update_invalid_cron_raises():
    job = SimpleNamespace(cron="0 8 * * *", enabled=True)
    db = MagicMock()
    db.flush = AsyncMock()
    with pytest.raises(UnprocessableError):
        await job_svc.update_scheduler_job(db, job, enabled=None, cron="not-cron")


@pytest.mark.asyncio
async def test_patch_does_not_require_binding_json():
    job = SimpleNamespace(cron="0 8 * * *", enabled=True, binding_id="b1")
    db = MagicMock()
    db.flush = AsyncMock()
    updated = await job_svc.update_scheduler_job(
        db, job, enabled=False, cron="0 9 * * *"
    )
    assert updated.cron == "0 9 * * *"
    assert updated.enabled is False
    db.flush.assert_awaited()


def test_job_scheduler_cron_change_does_not_catch_up():
    scheduler = JobScheduler(MagicMock())
    job = SimpleNamespace(id="j1", cron="0 8 * * *")
    now = datetime(2026, 8, 24, 15, 0)
    scheduler._apply_job_cron(job, now)
    job.cron = "*/5 * * * *"
    later = datetime(2026, 8, 24, 15, 4)
    scheduler._apply_job_cron(job, later)
    assert scheduler._next_fire["j1"] == datetime(2026, 8, 24, 15, 5)


def test_seconds_until_due_still_wakes_on_slot():
    due = datetime(2026, 8, 24, 15, 10, 0)
    assert seconds_until_due(due, datetime(2026, 8, 24, 15, 9, 52), 30.0) == 8.0
