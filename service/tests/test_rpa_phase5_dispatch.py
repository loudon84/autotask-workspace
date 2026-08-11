"""Phase 5 Worker lease / renew / finish / events contract tests."""

import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")
os.environ.setdefault("RPA_ENGINE_VALIDATE_BINDING", "false")
os.environ.setdefault("ARTIFACT_STORAGE", "local")

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestError, ConflictError
from app.models.enums import HumanActionType, RunEventType, RunStatus, TaskStatus
from app.schemas.dispatch import (
    BrowserSessionConfig,
    LeaseCommandConfig,
    RunFinishRequest,
    WorkerLeaseRenewRequest,
    WorkerLeaseRenewResponse,
    WorkerLeaseRequest,
    WorkerLeaseResponse,
)
from app.services import dispatch_service, human_action_service, rpa_engine_client, s3_storage
from app.services.task_state_machine import can_transition


REQUIRED_LEASE_FIELDS = {
    "taskId",
    "runId",
    "leaseId",
    "workflowBindingId",
    "portalAccountId",
    "rpaFlowId",
    "input",
    "tenantId",
    "workflowTemplateId",
    "workflowCode",
    "rpaEngineType",
    "rpaFlowVersion",
    "credentialRef",
    "config",
    "leaseExpiresAt",
}


def test_worker_lease_request_accepts_snake_case():
    body = WorkerLeaseRequest.model_validate(
        {"worker_id": "server-worker-001", "capabilities": ["PLAYWRIGHT_CDP"], "limit": 1}
    )
    assert body.worker_id == "server-worker-001"


def test_worker_lease_response_requires_snapshot_fields():
    with pytest.raises(ValidationError):
        WorkerLeaseResponse(
            task_id="t1",
            run_id="r1",
            lease_id="l1",
            workflow_binding_id="b1",
            portal_account_id="p1",
            rpa_flow_id="flow",
            input={},
        )

    payload = WorkerLeaseResponse(
        task_id="t1",
        run_id="r1",
        lease_id="l1",
        workflow_binding_id="b1",
        portal_account_id="p1",
        rpa_flow_id="rpa_flow_mock_srm_fetch_po",
        input={"po_no": "PO-20260708-001"},
        tenant_id="tenant-1",
        workflow_template_id="tpl-1",
        workflow_code="srm_fetch_po",
        rpa_engine_type="PLAYWRIGHT_CDP",
        rpa_flow_version="1.0.0",
        credential_ref="credential-ref-mock-srm",
        config=LeaseCommandConfig(
            portal_url="https://portal.example.com/srm",
            browser_session=BrowserSessionConfig(mode="MANAGED", channel="chrome"),
        ),
        lease_expires_at=datetime.now(UTC),
    )
    dumped = payload.model_dump(by_alias=True)
    assert REQUIRED_LEASE_FIELDS.issubset(dumped.keys())
    assert dumped["config"]["portalUrl"] == "https://portal.example.com/srm"
    assert dumped["config"]["browserSession"]["mode"] == "MANAGED"
    assert dumped["input"] == {"po_no": "PO-20260708-001"}


def test_renew_response_returns_lease_expires_at():
    expires = datetime.now(UTC) + timedelta(seconds=60)
    data = WorkerLeaseRenewResponse(lease_expires_at=expires)
    dumped = data.model_dump(by_alias=True)
    assert "leaseExpiresAt" in dumped
    assert dumped["leaseExpiresAt"] == expires


def test_running_can_requeue_after_lease_expire():
    assert can_transition(TaskStatus.RUNNING, TaskStatus.QUEUED)
    assert can_transition(TaskStatus.WAITING_HUMAN, TaskStatus.SUCCESS_MANUAL)
    assert not can_transition(TaskStatus.HUMAN_OPERATING, TaskStatus.RUNNING)


def test_normalize_checksum_strips_prefix():
    assert rpa_engine_client.normalize_checksum("sha256:AbCd") == "abcd"
    assert rpa_engine_client.normalize_checksum("ABCDEF") == "abcdef"


@pytest.mark.asyncio
async def test_renew_rejects_expired_lease():
    lease = MagicMock()
    lease.lease_expires_at = datetime.now(UTC) - timedelta(seconds=5)
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = lease
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(BadRequestError) as exc:
        await dispatch_service.renew_lease(
            db,
            "task-1",
            WorkerLeaseRenewRequest.model_validate({"worker_id": "w1", "lease_id": "lease-1"}),
        )
    assert exc.value.message_key == "errors.autotask.lease_expired"


@pytest.mark.asyncio
async def test_renew_success_returns_new_expiry():
    now = datetime.now(UTC)
    lease = MagicMock()
    lease.lease_expires_at = now + timedelta(seconds=30)
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = lease
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    async def _refresh(_obj):
        lease.lease_expires_at = now + timedelta(seconds=60)

    db.refresh.side_effect = _refresh

    resp = await dispatch_service.renew_lease(
        db,
        "task-1",
        WorkerLeaseRenewRequest.model_validate({"worker_id": "w1", "lease_id": "lease-1"}),
    )
    assert isinstance(resp, WorkerLeaseRenewResponse)
    assert resp.lease_expires_at >= now


@pytest.mark.asyncio
async def test_finish_waiting_human_idempotent():
    run = MagicMock()
    run.id = "run-1"
    run.task_id = "task-1"
    run.status = RunStatus.WAITING_HUMAN
    run.rpa_worker_id = "w1"
    run.current_step_id = "srm.search_po"

    task = MagicMock()
    task.id = "task-1"
    task.status = TaskStatus.WAITING_HUMAN
    task.portal_account_id = "portal-1"

    db = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "rpa_runs" in sql.lower() or "RpaRun" in sql:
            result.scalar_one_or_none.return_value = run
            return result
        if "automation_tasks" in sql.lower() or "AutomationTask" in sql:
            result.scalar_one_or_none.return_value = task
            return result
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        return result

    db.execute = AsyncMock(side_effect=_execute)

    finished = await dispatch_service.finish_run(
        db,
        "run-1",
        RunFinishRequest(status=RunStatus.WAITING_HUMAN, error_code="HUMAN_VERIFICATION_REQUIRED"),
    )
    assert finished.status == RunStatus.WAITING_HUMAN


@pytest.mark.asyncio
async def test_finish_terminal_conflict():
    run = MagicMock()
    run.id = "run-1"
    run.task_id = "task-1"
    run.status = RunStatus.SUCCESS

    task = MagicMock()
    task.id = "task-1"

    db = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "rpa_runs" in sql.lower() or "RpaRun" in sql:
            result.scalar_one_or_none.return_value = run
            return result
        result.scalar_one_or_none.return_value = task
        return result

    db.execute = AsyncMock(side_effect=_execute)

    with pytest.raises(ConflictError):
        await dispatch_service.finish_run(db, "run-1", RunFinishRequest(status=RunStatus.FAILED))


@pytest.mark.asyncio
async def test_confirm_resume_running_rejected():
    action = MagicMock()
    action.id = "ha-1"
    action.status = "PENDING"
    action.task_id = "task-1"
    action.run_id = "run-1"

    user = MagicMock()
    user.user_id = "u1"

    with patch.object(human_action_service, "get_human_action", AsyncMock(return_value=action)):
        with pytest.raises(BadRequestError) as exc:
            await human_action_service.confirm_human_action(
                AsyncMock(),
                "tenant-1",
                "ha-1",
                user,
                resume_running=True,
            )
    assert exc.value.message_key == "errors.autotask.human_resume_not_supported"
    assert exc.value.details["error_code"] == "HUMAN_RESUME_NOT_SUPPORTED"


def test_step_event_types_include_waiting_human():
    assert RunEventType.STEP_WAITING_HUMAN == "STEP_WAITING_HUMAN"
    assert HumanActionType.CAPTCHA_OR_MFA == "CAPTCHA_OR_MFA"


def test_local_upload_url_is_absolute():
    url = s3_storage.local_upload_url("tenant/task/run/file.png")
    assert url.startswith("http")
    assert "/api/v1/autotask/artifacts/upload/" in url


def test_response_from_snapshot_does_not_use_latest_binding():
    snapshot = {
        "taskId": "t1",
        "workflowBindingId": "b1",
        "portalAccountId": "p1",
        "tenantId": "tenant-1",
        "workflowTemplateId": "tpl-1",
        "workflowCode": "srm_fetch_po",
        "rpaEngineType": "PLAYWRIGHT_CDP",
        "rpaFlowId": "rpa_flow_mock_srm_fetch_po",
        "rpaFlowVersion": "1.0.0",
        "credentialRef": "credential-ref-mock-srm",
        "input": {"po_no": "PO-20260708-001"},
        "config": {
            "portalUrl": "https://portal.example.com/srm-original",
            "browserSession": {
                "mode": "MANAGED",
                "headless": True,
                "channel": "chrome",
                "profileRef": None,
                "cdpEndpointRef": None,
                "closePolicy": "CLOSE_ON_FINISH",
            },
        },
    }
    resp = dispatch_service._response_from_snapshot(
        snapshot=snapshot,
        run_id="run-1",
        lease_id="lease-1",
        lease_expires_at=datetime.now(UTC),
    )
    assert resp.config.portal_url == "https://portal.example.com/srm-original"
    assert resp.rpa_flow_version == "1.0.0"
