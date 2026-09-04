"""Phase 5 Worker lease / renew / finish / events contract tests."""

import os
import json

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
    "credentials",
    "config",
    "leaseExpiresAt",
}


def test_lease_module_has_worker_ttl_settings() -> None:
    assert dispatch_service.settings.WORKER_LEASE_TTL_SECONDS >= 1


def test_worker_lease_request_accepts_snake_case():
    body = WorkerLeaseRequest.model_validate(
        {"worker_id": "server-worker-001", "capabilities": ["PLAYWRIGHT_CDP"], "limit": 1}
    )
    assert body.worker_id == "server-worker-001"


def test_lease_command_config_includes_dry_run():
    cfg = LeaseCommandConfig(
        portal_url="https://supplier.tiandy.com",
        browser_session=BrowserSessionConfig(mode="MANAGED", channel="chrome"),
        dry_run=True,
    )
    dumped = cfg.model_dump(by_alias=True)
    assert dumped["dryRun"] is True
    assert dumped["portalUrl"] == "https://supplier.tiandy.com"


def test_lease_command_config_dry_run_defaults_false():
    cfg = LeaseCommandConfig(
        portal_url="https://portal.example.com/srm",
        browser_session=BrowserSessionConfig(mode="MANAGED", channel="chrome"),
    )
    assert cfg.dry_run is False
    assert cfg.model_dump(by_alias=True)["dryRun"] is False


def test_build_command_snapshot_includes_dry_run_from_binding():
    task = MagicMock()
    task.id = "t1"
    task.tenant_id = "tenant-1"
    task.input = "{}"
    binding = MagicMock()
    binding.id = "b1"
    binding.config = '{"dryRun": true, "browserSession": {"mode": "MANAGED", "channel": "chrome"}}'
    binding.rpa_engine_type = "PLAYWRIGHT_CDP"
    binding.rpa_flow_id = "flow"
    binding.rpa_flow_version = "1.0.0"
    binding.rpa_flow_version_id = "fv1"
    binding.flow_checksum_snapshot = "abc"
    template = MagicMock()
    template.id = "tpl1"
    template.code = "code"
    portal = MagicMock()
    portal.id = "p1"
    portal.portal_url = "https://supplier.tiandy.com"
    portal.credential_ref = "srm-password"
    portal.login_account = "02556"
    portal.erp_entity_name = "天地伟业"
    portal.erp_entity_code = "C007193-01_104"
    portal.business_entity = "深圳市芯云信息科技有限公司"
    portal.ou = "104"

    with patch.object(dispatch_service, "task_input_dict", return_value={}):
        snapshot = dispatch_service._build_command_snapshot(
            task=task, binding=binding, template=template, portal=portal
        )
    assert snapshot["config"]["dryRun"] is True
    assert snapshot["config"]["portalUrl"] == "https://supplier.tiandy.com"
    assert snapshot["config"]["customerName"] == "天地伟业"
    assert snapshot["config"]["customerCode"] == "C007193-01_104"
    assert snapshot["config"]["businessEntity"] == "深圳市芯云信息科技有限公司"
    assert snapshot["config"]["ou"] == "104"
    assert snapshot["config"]["searches"] is None
    assert snapshot["credentials"] == {"username": "02556", "password": "srm-password"}
    assert snapshot["credentialRef"] == ""

    response = dispatch_service._response_from_snapshot(
        snapshot=snapshot,
        run_id="r1",
        lease_id="l1",
        lease_expires_at=datetime.now(UTC),
    )
    assert response.config.dry_run is True
    assert response.model_dump(by_alias=True)["config"]["dryRun"] is True


def test_build_command_snapshot_dry_run_false_when_absent():
    task = MagicMock()
    task.id = "t1"
    task.tenant_id = "tenant-1"
    binding = MagicMock()
    binding.id = "b1"
    binding.config = '{"browserSession": {"mode": "MANAGED"}}'
    binding.rpa_engine_type = "PLAYWRIGHT_CDP"
    binding.rpa_flow_id = "flow"
    binding.rpa_flow_version = "1.0.0"
    binding.rpa_flow_version_id = "fv1"
    binding.flow_checksum_snapshot = "abc"
    template = MagicMock()
    template.id = "tpl1"
    template.code = "code"
    portal = MagicMock()
    portal.id = "p1"
    portal.portal_url = "http://192.168.102.247:3000"
    portal.credential_ref = "demo-password"
    portal.login_account = "demo"
    portal.erp_entity_name = "示例客户"
    portal.erp_entity_code = "CUST-001"
    portal.business_entity = ""
    portal.ou = ""

    with patch.object(dispatch_service, "task_input_dict", return_value={}):
        snapshot = dispatch_service._build_command_snapshot(
            task=task, binding=binding, template=template, portal=portal
        )
    assert snapshot["config"]["dryRun"] is False
    assert snapshot["config"]["businessEntity"] is None
    assert snapshot["config"]["ou"] is None
    assert snapshot["config"]["searches"] is None


def test_build_command_snapshot_copies_searches_from_binding():
    task = MagicMock()
    task.id = "t1"
    task.tenant_id = "tenant-1"
    binding = MagicMock()
    binding.id = "b1"
    binding.config = json.dumps(
        {
            "portalUrl": "https://supplier.tiandy.com",
            "browserSession": {"mode": "MANAGED", "channel": "chrome"},
            "searches": [
                {"replyStatus": "待签章"},
                {"poNo": "POJS2607170008", "treatAsPending": True},
            ],
        },
        ensure_ascii=False,
    )
    binding.rpa_engine_type = "PLAYWRIGHT_CDP"
    binding.rpa_flow_id = "rpa_flow_srm_scan_pending_orders"
    binding.rpa_flow_version = "1.1.3"
    binding.rpa_flow_version_id = "fv-scan"
    binding.flow_checksum_snapshot = "abc"
    template = MagicMock()
    template.id = "tpl1"
    template.code = "srm_scan_pending_orders"
    portal = MagicMock()
    portal.id = "p1"
    portal.portal_url = "https://supplier.tiandy.com"
    portal.credential_ref = "srm-password"
    portal.login_account = "02556"
    portal.erp_entity_name = "天地伟业"
    portal.erp_entity_code = "C007193-01_104"
    portal.business_entity = "深圳市芯云信息科技有限公司"
    portal.ou = "104"

    with patch.object(dispatch_service, "task_input_dict", return_value={}):
        snapshot = dispatch_service._build_command_snapshot(
            task=task, binding=binding, template=template, portal=portal
        )
    assert snapshot["config"]["searches"] == [
        {"replyStatus": "待签章"},
        {"poNo": "POJS2607170008", "treatAsPending": True},
    ]
    assert snapshot["input"]["searches"] == snapshot["config"]["searches"]
    response = dispatch_service._response_from_snapshot(
        snapshot=snapshot,
        run_id="r1",
        lease_id="l1",
        lease_expires_at=datetime.now(UTC),
    )
    assert response.config.searches == [
        {"replyStatus": "待签章"},
        {"poNo": "POJS2607170008", "treatAsPending": True},
    ]
    assert response.model_dump(by_alias=True)["config"]["searches"][1]["poNo"] == "POJS2607170008"


def test_build_command_snapshot_copies_task_env_bases(monkeypatch):
    task = MagicMock()
    task.id = "t1"
    task.tenant_id = "tenant-1"
    binding = MagicMock()
    binding.id = "b1"
    binding.config = '{"browserSession": {"mode": "MANAGED"}}'
    binding.rpa_engine_type = "PLAYWRIGHT_CDP"
    binding.rpa_flow_id = "flow"
    binding.rpa_flow_version = "1.0.0"
    binding.rpa_flow_version_id = "fv1"
    binding.flow_checksum_snapshot = "abc"
    template = MagicMock()
    template.id = "tpl1"
    template.code = "code"
    portal = MagicMock()
    portal.id = "p1"
    portal.portal_url = "https://portal.example.com"
    portal.credential_ref = "pw"
    portal.login_account = "user1"
    portal.erp_entity_name = "客户A"
    portal.erp_entity_code = "SITE-1"
    portal.business_entity = "深圳市芯云信息科技有限公司"
    portal.ou = "104"

    monkeypatch.setattr("app.services.runtime_endpoints.settings.SDMS_BASE_URL", "http://sdms.example")
    monkeypatch.setattr("app.services.runtime_endpoints.settings.ERP_BASE_URL", "http://erp.example")
    monkeypatch.setattr("app.services.runtime_endpoints.settings.OA_BASE_URL", "")
    monkeypatch.setattr(
        "app.services.runtime_endpoints.settings.SDMS_ATTACHMENT_API_BASE_URL",
        "http://doc.example",
    )
    monkeypatch.setattr("app.services.runtime_endpoints.settings.ERP_CLIENT_ID", "smc_erp")
    monkeypatch.setattr("app.services.runtime_endpoints.settings.ERP_CLIENT_SECRET", "secret")

    with patch.object(dispatch_service, "task_input_dict", return_value={}):
        snapshot = dispatch_service._build_command_snapshot(
            task=task, binding=binding, template=template, portal=portal
        )
    assert snapshot["config"]["sdmsBaseUrl"] == "http://sdms.example"
    assert snapshot["config"]["erpBaseUrl"] == "http://erp.example"
    assert snapshot["config"]["docBaseUrl"] == "http://doc.example"
    assert snapshot["config"]["erpClientId"] == "smc_erp"
    assert snapshot["config"]["erpClientSecret"] == "secret"
    assert "erpTokenUrl" not in snapshot["config"]
    response = dispatch_service._response_from_snapshot(
        snapshot=snapshot,
        run_id="r1",
        lease_id="l1",
        lease_expires_at=datetime.now(UTC),
    )
    assert response.config.erp_base_url == "http://erp.example"
    assert response.credentials.password == "pw"


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
        credential_ref="",
        credentials={"username": "buyer", "password": "secret"},
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
    assert dumped["credentials"]["username"] == "buyer"
    assert dumped["credentials"]["password"] == "secret"


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


def test_queued_can_cancel_when_portal_disabled():
    assert can_transition(TaskStatus.QUEUED, TaskStatus.CANCELLED)


def test_validate_snapshot_sources_rejects_disabled_portal():
    portal = MagicMock()
    portal.status = "DISABLED"
    portal.tenant_id = "t1"
    portal.portal_url = "http://example.test"
    portal.credential_ref = "secret"
    portal.login_account = "user"
    binding = MagicMock()
    binding.status = "ENABLED"
    binding.rpa_flow_version_id = "v1"
    binding.flow_checksum_snapshot = "abc"
    binding.config = "{}"
    template = MagicMock()
    template.tenant_id = "t1"
    task = MagicMock()
    task.tenant_id = "t1"
    with pytest.raises(BadRequestError) as exc:
        dispatch_service._validate_snapshot_sources(
            binding=binding, portal=portal, template=template, task=task
        )
    assert exc.value.message_key == "errors.autotask.portal_disabled"


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
        "credentialRef": "",
        "credentials": {"username": "buyer", "password": "secret"},
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
    assert resp.credentials is not None
    assert resp.credentials.username == "buyer"
    assert resp.credentials.password == "secret"
