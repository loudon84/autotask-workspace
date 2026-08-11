"""Worker dispatch: lease, events, finish."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import (
    BindingStatus,
    HumanActionType,
    PortalAccountStatus,
    RunEventType,
    RunStatus,
    TaskStatus,
    WorkerStatus,
)
from app.models.human_action import HumanAction
from app.models.portal_account import PortalAccount
from app.models.rpa_run import RpaRun
from app.models.rpa_worker import RpaWorker
from app.models.run_event import RunEvent
from app.models.step_run import StepRun
from app.models.worker_lease import WorkerLease
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.schemas.dispatch import (
    BrowserSessionConfig,
    LeaseCommandConfig,
    RunArtifactCreate,
    RunEventCreate,
    RunFinishRequest,
    WorkerLeaseRenewRequest,
    WorkerLeaseRenewResponse,
    WorkerLeaseRequest,
    WorkerLeaseResponse,
)
from app.services.artifact_service import create_artifact_record, find_artifact_by_storage_key
from app.services.automation_task_service import task_input_dict
from app.services.human_action_service import create_human_action_for_run
from app.services.json_utils import dumps_json, loads_json
from app.services.rpa_worker_service import get_worker
from app.services.task_state_machine import transition
from app.services.task_successor_service import enqueue_successor_job

TERMINAL_RUN_STATUSES = {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.WAITING_HUMAN}


def _parse_binding_config(raw: str | dict | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _browser_session_from_config(config: dict[str, Any]) -> BrowserSessionConfig:
    raw = config.get("browserSession") or config.get("browser_session") or {}
    if not isinstance(raw, dict):
        raw = {}
    return BrowserSessionConfig(
        mode=raw.get("mode", "MANAGED"),
        headless=bool(raw.get("headless", True)),
        channel=raw.get("channel", "chrome"),
        profile_ref=raw.get("profileRef") or raw.get("profile_ref"),
        cdp_endpoint_ref=raw.get("cdpEndpointRef") or raw.get("cdp_endpoint_ref"),
        close_policy=raw.get("closePolicy") or raw.get("close_policy") or "CLOSE_ON_FINISH",
    )


def _build_command_snapshot(
    *,
    task: AutomationTask,
    binding: WorkflowBinding,
    template: WorkflowTemplate,
    portal: PortalAccount,
) -> dict[str, Any]:
    binding_config = _parse_binding_config(binding.config)
    browser_session = _browser_session_from_config(binding_config)
    portal_url = portal.portal_url
    if binding_config.get("portalUrl"):
        portal_url = binding_config["portalUrl"]
    credential_ref = portal.credential_ref or ""
    return {
        "taskId": task.id,
        "workflowBindingId": binding.id,
        "portalAccountId": portal.id,
        "tenantId": task.tenant_id,
        "workflowTemplateId": template.id,
        "workflowCode": template.code,
        "rpaEngineType": binding.rpa_engine_type,
        "rpaFlowId": binding.rpa_flow_id,
        "rpaFlowVersion": binding.rpa_flow_version,
        "rpaFlowVersionId": binding.rpa_flow_version_id,
        "flowChecksumSnapshot": binding.flow_checksum_snapshot,
        "credentialRef": credential_ref,
        "input": task_input_dict(task),
        "config": {
            "portalUrl": portal_url,
            "browserSession": browser_session.model_dump(by_alias=True),
        },
    }


def _response_from_snapshot(
    *,
    snapshot: dict[str, Any],
    run_id: str,
    lease_id: str,
    lease_expires_at: datetime,
) -> WorkerLeaseResponse:
    config_raw = snapshot.get("config") or {}
    browser_raw = config_raw.get("browserSession") or {}
    return WorkerLeaseResponse(
        task_id=snapshot["taskId"],
        run_id=run_id,
        lease_id=lease_id,
        workflow_binding_id=snapshot["workflowBindingId"],
        portal_account_id=snapshot["portalAccountId"],
        rpa_flow_id=snapshot["rpaFlowId"],
        input=snapshot.get("input") or {},
        tenant_id=snapshot["tenantId"],
        workflow_template_id=snapshot["workflowTemplateId"],
        workflow_code=snapshot["workflowCode"],
        rpa_engine_type=snapshot["rpaEngineType"],
        rpa_flow_version=snapshot["rpaFlowVersion"],
        credential_ref=snapshot.get("credentialRef") or "",
        config=LeaseCommandConfig(
            portal_url=config_raw.get("portalUrl") or "",
            browser_session=BrowserSessionConfig(
                mode=browser_raw.get("mode", "MANAGED"),
                headless=bool(browser_raw.get("headless", True)),
                channel=browser_raw.get("channel", "chrome"),
                profile_ref=browser_raw.get("profileRef"),
                cdp_endpoint_ref=browser_raw.get("cdpEndpointRef"),
                close_policy=browser_raw.get("closePolicy", "CLOSE_ON_FINISH"),
            ),
        ),
        lease_expires_at=lease_expires_at,
    )


def _validate_snapshot_sources(
    *,
    binding: WorkflowBinding,
    portal: PortalAccount,
    template: WorkflowTemplate,
    task: AutomationTask,
) -> None:
    if binding.status != BindingStatus.ENABLED:
        raise BadRequestError(message="工作流绑定未启用", message_key="errors.autotask.binding_disabled")
    if portal.status != PortalAccountStatus.ENABLED:
        raise BadRequestError(message="门户账号未启用", message_key="errors.autotask.portal_disabled")
    if portal.tenant_id != task.tenant_id or template.tenant_id != task.tenant_id:
        raise BadRequestError(message="任务与绑定租户不一致", message_key="errors.autotask.tenant_mismatch")
    if not binding.rpa_flow_version_id or not binding.flow_checksum_snapshot:
        raise BadRequestError(
            message="绑定缺少 Flow 版本快照，禁止领取",
            message_key="errors.autotask.binding_flow_snapshot_missing",
            details={"error_code": "BINDING_FLOW_SNAPSHOT_MISSING"},
        )
    binding_config = _parse_binding_config(binding.config)
    portal_url = binding_config.get("portalUrl") or portal.portal_url
    if not portal_url:
        raise BadRequestError(message="缺少 portalUrl", message_key="errors.autotask.portal_url_missing")
    browser = _browser_session_from_config(binding_config)
    if browser.mode != "MANAGED":
        raise BadRequestError(
            message="仅支持 MANAGED 浏览器会话模式",
            message_key="errors.autotask.browser_session_not_managed",
        )
    if not portal.credential_ref:
        raise BadRequestError(message="门户缺少 credentialRef", message_key="errors.autotask.credential_ref_missing")


async def _expire_stale_leases(db: AsyncSession) -> None:
    now = datetime.now(UTC)
    stale_leases = (
        await db.execute(
            select(WorkerLease).where(
                WorkerLease.lease_expires_at < now,
                not_deleted(WorkerLease),
            )
        )
    ).scalars().all()
    for lease in stale_leases:
        task = (
            await db.execute(
                select(AutomationTask).where(AutomationTask.id == lease.task_id, not_deleted(AutomationTask))
            )
        ).scalar_one_or_none()
        if task and task.status in {TaskStatus.LEASED, TaskStatus.RUNNING}:
            transition(task, TaskStatus.QUEUED)
        lease.soft_delete()
    if stale_leases:
        await db.flush()


async def _load_binding_context(
    db: AsyncSession, task: AutomationTask
) -> tuple[WorkflowBinding, WorkflowTemplate, PortalAccount]:
    binding = (
        await db.execute(
            select(WorkflowBinding).where(
                WorkflowBinding.id == task.workflow_binding_id,
                not_deleted(WorkflowBinding),
            )
        )
    ).scalar_one_or_none()
    if binding is None:
        raise NotFoundError(message="工作流绑定不存在", message_key="errors.autotask.binding_not_found")

    template = (
        await db.execute(
            select(WorkflowTemplate).where(
                WorkflowTemplate.id == binding.workflow_template_id,
                not_deleted(WorkflowTemplate),
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise NotFoundError(message="工作流模板不存在", message_key="errors.autotask.template_not_found")

    portal = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == task.portal_account_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if portal is None:
        raise NotFoundError(message="门户账号不存在", message_key="errors.autotask.portal_not_found")

    return binding, template, portal


async def lease_task(db: AsyncSession, body: WorkerLeaseRequest) -> WorkerLeaseResponse | None:
    await _expire_stale_leases(db)
    worker = await get_worker(db, body.worker_id)

    stmt = (
        select(AutomationTask)
        .where(
            AutomationTask.status == TaskStatus.QUEUED,
            not_deleted(AutomationTask),
        )
        .order_by(AutomationTask.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(body.limit)
    )
    tasks = (await db.execute(stmt)).scalars().all()
    if not tasks:
        return None

    task = tasks[0]
    binding, template, portal = await _load_binding_context(db, task)

    existing_run = (
        await db.execute(
            select(RpaRun)
            .where(
                RpaRun.task_id == task.id,
                RpaRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
                not_deleted(RpaRun),
            )
            .order_by(RpaRun.created_at.desc())
            .with_for_update()
        )
    ).scalar_one_or_none()

    lease_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.WORKER_LEASE_TTL_SECONDS)

    if existing_run is not None and existing_run.command_snapshot:
        run = existing_run
        snapshot = dict(existing_run.command_snapshot)
    else:
        _validate_snapshot_sources(binding=binding, portal=portal, template=template, task=task)
        snapshot = _build_command_snapshot(task=task, binding=binding, template=template, portal=portal)
        if existing_run is None:
            run = RpaRun(
                task_id=task.id,
                rpa_flow_id=binding.rpa_flow_id,
                status=RunStatus.QUEUED,
                command_snapshot=snapshot,
            )
            db.add(run)
            await db.flush()
        else:
            run = existing_run
            run.command_snapshot = snapshot

    transition(task, TaskStatus.LEASED)
    run.lease_id = lease_id
    run.rpa_worker_id = body.worker_id
    run.status = RunStatus.RUNNING
    if run.started_at is None:
        run.started_at = datetime.now(UTC)
    run.ended_at = None
    worker.status = WorkerStatus.BUSY
    worker.current_run_id = run.id
    db.add(
        WorkerLease(
            task_id=task.id,
            run_id=run.id,
            worker_id=body.worker_id,
            lease_id=lease_id,
            lease_expires_at=expires_at,
        )
    )
    db.add(
        RunEvent(
            run_id=run.id,
            task_id=task.id,
            worker_id=body.worker_id,
            type=RunEventType.RUN_STARTED,
            level="INFO",
            message="任务已被 Worker 领取",
            payload=dumps_json({"leaseId": lease_id}),
        )
    )
    transition(task, TaskStatus.RUNNING)
    await db.commit()

    return _response_from_snapshot(
        snapshot=snapshot,
        run_id=run.id,
        lease_id=lease_id,
        lease_expires_at=expires_at,
    )


async def renew_lease(db: AsyncSession, task_id: str, body: WorkerLeaseRenewRequest) -> WorkerLeaseRenewResponse:
    lease = (
        await db.execute(
            select(WorkerLease)
            .where(
                WorkerLease.task_id == task_id,
                WorkerLease.worker_id == body.worker_id,
                WorkerLease.lease_id == body.lease_id,
                not_deleted(WorkerLease),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if lease is None:
        raise NotFoundError(message="Lease 不存在", message_key="errors.autotask.lease_not_found")

    now = datetime.now(UTC)
    expires = lease.lease_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < now:
        raise BadRequestError(message="租约已过期", message_key="errors.autotask.lease_expired")

    lease.lease_expires_at = now + timedelta(seconds=settings.WORKER_LEASE_TTL_SECONDS)
    await db.commit()
    await db.refresh(lease)
    return WorkerLeaseRenewResponse(lease_expires_at=lease.lease_expires_at)


async def _upsert_step_run(
    db: AsyncSession,
    *,
    run_id: str,
    step_id: str,
    step_name: str,
    status: str,
) -> StepRun:
    step = (
        await db.execute(
            select(StepRun).where(
                StepRun.run_id == run_id,
                StepRun.step_id == step_id,
                not_deleted(StepRun),
            )
        )
    ).scalar_one_or_none()
    if step is None:
        step = StepRun(run_id=run_id, step_id=step_id, step_name=step_name or step_id, status=status)
        db.add(step)
    else:
        step.status = status
        if step_name:
            step.step_name = step_name
        elif not step.step_name:
            step.step_name = step_id
    await db.flush()
    return step


async def append_run_event(db: AsyncSession, run_id: str, body: RunEventCreate) -> RunEvent:
    run = (
        await db.execute(select(RpaRun).where(RpaRun.id == run_id, not_deleted(RpaRun)))
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(message="Run 不存在", message_key="errors.autotask.run_not_found")

    task = (
        await db.execute(select(AutomationTask).where(AutomationTask.id == run.task_id, not_deleted(AutomationTask)))
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    payload = body.payload or {}
    event = RunEvent(
        run_id=run.id,
        task_id=task.id,
        worker_id=body.worker_id,
        type=body.type,
        level=body.level,
        message=body.message,
        payload=dumps_json(payload),
    )
    db.add(event)

    step_id = payload.get("stepId") or payload.get("step_id")
    step_name = payload.get("stepName") or payload.get("step_name") or step_id or ""

    if body.type == RunEventType.STEP_STARTED and step_id:
        await _upsert_step_run(db, run_id=run.id, step_id=step_id, step_name=step_name, status="RUNNING")
        run.current_step_id = step_id
        task.current_step = step_id
    elif body.type == RunEventType.STEP_SUCCEEDED and step_id:
        await _upsert_step_run(db, run_id=run.id, step_id=step_id, step_name=step_name, status="SUCCESS")
    elif body.type == RunEventType.STEP_FAILED and step_id:
        await _upsert_step_run(db, run_id=run.id, step_id=step_id, step_name=step_name, status="FAILED")
    elif body.type == RunEventType.STEP_WAITING_HUMAN and step_id:
        await _upsert_step_run(db, run_id=run.id, step_id=step_id, step_name=step_name, status="WAITING_HUMAN")
        run.current_step_id = step_id
        task.current_step = step_id
    elif body.type == RunEventType.WAITING_HUMAN and step_id:
        await _upsert_step_run(db, run_id=run.id, step_id=step_id, step_name=step_name, status="WAITING_HUMAN")

    await db.commit()
    await db.refresh(event)
    return event


async def append_run_artifact(db: AsyncSession, run_id: str, body: RunArtifactCreate, created_by: str | None) -> None:
    run = (
        await db.execute(select(RpaRun).where(RpaRun.id == run_id, not_deleted(RpaRun)))
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(message="Run 不存在", message_key="errors.autotask.run_not_found")
    task = (
        await db.execute(select(AutomationTask).where(AutomationTask.id == run.task_id, not_deleted(AutomationTask)))
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    expected_prefix = f"{task.tenant_id}/{task.id}/{run.id}/"
    if not body.storage_key.startswith(f"{task.tenant_id}/{task.id}/"):
        raise BadRequestError(
            message="storageKey 不在本次上传范围内",
            message_key="errors.autotask.storage_key_out_of_scope",
        )

    existing = await find_artifact_by_storage_key(db, run_id=run.id, storage_key=body.storage_key)
    if existing is not None:
        return

    await create_artifact_record(
        db,
        tenant_id=task.tenant_id,
        task_id=task.id,
        run_id=run.id,
        artifact_type=body.type,
        name=body.name,
        storage_key=body.storage_key,
        size=body.size,
        mime_type=body.mime_type,
        created_by=created_by,
    )
    db.add(
        RunEvent(
            run_id=run.id,
            task_id=task.id,
            type=RunEventType.ARTIFACT_SAVED,
            level="INFO",
            message=f"Artifact 已保存: {body.name}",
            payload=dumps_json({"storageKey": body.storage_key, "expectedPrefix": expected_prefix}),
        )
    )
    await db.commit()


async def _latest_waiting_step_id(db: AsyncSession, run_id: str) -> str | None:
    event = (
        await db.execute(
            select(RunEvent)
            .where(
                RunEvent.run_id == run_id,
                RunEvent.type.in_([RunEventType.STEP_WAITING_HUMAN, RunEventType.WAITING_HUMAN]),
                not_deleted(RunEvent),
            )
            .order_by(RunEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if event is None:
        return None
    payload = loads_json(event.payload, {}) if event.payload else {}
    if isinstance(payload, dict):
        return payload.get("stepId") or payload.get("step_id")
    return None


async def finish_run(db: AsyncSession, run_id: str, body: RunFinishRequest) -> RpaRun:
    run = (
        await db.execute(
            select(RpaRun).where(RpaRun.id == run_id, not_deleted(RpaRun)).with_for_update()
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(message="Run 不存在", message_key="errors.autotask.run_not_found")
    task = (
        await db.execute(
            select(AutomationTask)
            .where(AutomationTask.id == run.task_id, not_deleted(AutomationTask))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    if run.status in TERMINAL_RUN_STATUSES:
        if run.status == body.status:
            return run
        raise ConflictError(
            message=f"Run 已处于终态 {run.status}，不允许覆盖为 {body.status}",
            message_key="errors.autotask.run_terminal_conflict",
        )

    if body.status not in {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.WAITING_HUMAN, RunStatus.CANCELLED}:
        raise BadRequestError(message="不支持的 Run 完成状态", message_key="errors.autotask.invalid_run_status")

    run.status = body.status
    run.ended_at = datetime.now(UTC)
    run.error_code = body.error_code
    run.error_message = body.error_message
    run.output = body.output if body.status == RunStatus.SUCCESS else None

    if body.status == RunStatus.SUCCESS:
        transition(task, TaskStatus.SUCCESS)
        task.progress = 100
        event_type = RunEventType.RUN_SUCCEEDED
        source_binding = (
            await db.execute(
                select(WorkflowBinding).where(
                    WorkflowBinding.id == task.workflow_binding_id,
                    not_deleted(WorkflowBinding),
                )
            )
        ).scalar_one_or_none()
        if source_binding is not None:
            await enqueue_successor_job(
                db,
                source_task=task,
                source_run=run,
                source_binding=source_binding,
            )
    elif body.status == RunStatus.FAILED:
        transition(task, TaskStatus.FAILED)
        event_type = RunEventType.RUN_FAILED
    elif body.status == RunStatus.CANCELLED:
        transition(task, TaskStatus.CANCELLED)
        event_type = RunEventType.RUN_CANCELLED
    else:
        transition(task, TaskStatus.WAITING_HUMAN)
        event_type = RunEventType.WAITING_HUMAN
        portal = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.id == task.portal_account_id,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
        step_id = await _latest_waiting_step_id(db, run.id) or run.current_step_id
        existing_action = (
            await db.execute(
                select(HumanAction).where(
                    HumanAction.run_id == run.id,
                    HumanAction.status.in_(["PENDING", "OPENED"]),
                    not_deleted(HumanAction),
                )
            )
        ).scalar_one_or_none()
        if existing_action is None:
            await create_human_action_for_run(
                db,
                task=task,
                run=run,
                action_type=HumanActionType.CAPTCHA_OR_MFA,
                title="需要人工完成 Mock SRM 验证",
                instruction="请打开门户完成验证；服务器浏览器会话已关闭",
                target_url=portal.portal_url if portal else None,
                payload={
                    "runId": run.id,
                    "stepId": step_id,
                    "errorCode": body.error_code,
                },
            )

    worker = None
    if run.rpa_worker_id:
        worker = (
            await db.execute(
                select(RpaWorker).where(RpaWorker.worker_id == run.rpa_worker_id, not_deleted(RpaWorker))
            )
        ).scalar_one_or_none()
    if worker:
        worker.current_run_id = None
        worker.status = WorkerStatus.ONLINE

    leases = (
        await db.execute(
            select(WorkerLease).where(WorkerLease.run_id == run.id, not_deleted(WorkerLease))
        )
    ).scalars().all()
    for lease in leases:
        lease.soft_delete()

    db.add(
        RunEvent(
            run_id=run.id,
            task_id=task.id,
            worker_id=run.rpa_worker_id,
            type=event_type,
            level="INFO" if body.status == RunStatus.SUCCESS else "ERROR",
            message=body.error_message or f"Run 已完成: {body.status}",
            payload=dumps_json({"status": body.status}),
        )
    )
    await db.commit()
    await db.refresh(run)
    return run
