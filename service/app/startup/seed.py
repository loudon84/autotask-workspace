"""Seed AutoTask mock data (idempotent / partial re-seed)."""

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.artifact import Artifact
from app.models.audit_log import AuditLog
from app.models.automation_task import AutomationTask
from app.models.autotask_setting import AutotaskSetting
from app.models.base import BaseModel, not_deleted
from app.models.portal_access_grant import PortalAccessGrant
from app.models.portal_account import PortalAccount
from app.models.rpa_component import RpaComponent
from app.models.rpa_run import RpaRun
from app.models.rpa_worker import RpaWorker
from app.models.run_event import RunEvent
from app.models.step_run import StepRun
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json

logger = logging.getLogger(__name__)

DEFAULT_TENANT_ID = "seed-tenant-001"
DEFAULT_USER_ID = "seed-user-001"

_SEED_SKIP_ERRORS = (ProgrammingError, OperationalError, DBAPIError, IntegrityError)


def _seed_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "seed"


def _load_json(name: str) -> list | dict:
    path = _seed_dir() / name
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _is_schema_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    markers = (
        "undefinedtable",
        "undefinedcolumn",
        "undefinedobject",
        "does not exist",
        "no such table",
        "relation ",
        "column ",
    )
    return any(marker in text for marker in markers)


async def _exists_by_id(db: AsyncSession, model: type[BaseModel], entity_id: str | None) -> bool:
    if not entity_id:
        return False
    row = (
        await db.execute(select(model.id).where(model.id == entity_id).limit(1))
    ).scalar_one_or_none()
    return row is not None


async def _seed_group(
    db: AsyncSession,
    group_name: str,
    runner: Callable[[], Awaitable[tuple[int, int]]],
) -> tuple[int, int]:
    """Run one seed group under a savepoint. Missing schema skips the group."""
    try:
        async with db.begin_nested():
            inserted, skipped = await runner()
        if inserted or skipped:
            logger.info("种子组 %s：新增 %s，已存在跳过 %s", group_name, inserted, skipped)
        else:
            logger.info("种子组 %s：无数据", group_name)
        return inserted, skipped
    except _SEED_SKIP_ERRORS as exc:
        if _is_schema_error(exc):
            logger.warning(
                "种子组 %s 跳过：表/索引/列不可用（请先 alembic upgrade head）。原因: %s",
                group_name,
                exc,
            )
            return 0, 0
        logger.warning("种子组 %s 跳过：%s", group_name, exc)
        return 0, 0


async def _seed_portal_accounts(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("srm-portals.json"):
        entity_id = item.get("id")
        if await _exists_by_id(db, PortalAccount, entity_id):
            skipped += 1
            continue
        db.add(
            PortalAccount(
                id=entity_id,
                tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                entity_type=item["entityType"],
                erp_entity_code=item["erpEntityCode"],
                erp_entity_name=item["erpEntityName"],
                portal_name=item["portalName"],
                portal_url=item["portalUrl"],
                login_account=item["loginAccount"],
                credential_ref=item.get("credentialRef"),
                client_open_mode=item.get("clientOpenMode", "webcontents"),
                client_session_partition=item.get("clientSessionPartition", ""),
                rpa_profile_id=item.get("rpaProfileId"),
                status=item.get("status", "ENABLED"),
                owner_dept_id=item.get("ownerDeptId"),
                created_by=item.get("createdBy", DEFAULT_USER_ID),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_portal_access_grants(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("portal-access-grants.json"):
        entity_id = item.get("id")
        if await _exists_by_id(db, PortalAccessGrant, entity_id):
            skipped += 1
            continue
        db.add(
            PortalAccessGrant(
                id=entity_id,
                portal_account_id=item["portalAccountId"],
                subject_type=item["subjectType"],
                subject_id=item["subjectId"],
                permissions=dumps_json(item.get("permissions", [])),
                granted_by=item.get("grantedBy", DEFAULT_USER_ID),
                granted_at=item.get("grantedAt", datetime.now(UTC).isoformat()),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_workflow_templates(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("workflow-templates.json"):
        entity_id = item.get("id")
        if await _exists_by_id(db, WorkflowTemplate, entity_id):
            skipped += 1
            continue
        db.add(
            WorkflowTemplate(
                id=entity_id,
                tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                name=item["name"],
                code=item["code"],
                description=item.get("description"),
                entity_type=item["entityType"],
                category=item.get("category", ""),
                status=item.get("status", "ENABLED"),
                version=item.get("version", "1.0.0"),
                input_schema=dumps_json(item.get("inputSchema", [])),
                business_steps=dumps_json(item.get("businessSteps", [])),
                created_by=item.get("createdBy", DEFAULT_USER_ID),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_workflow_bindings(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("workflow-bindings.json"):
        entity_id = item.get("id")
        if await _exists_by_id(db, WorkflowBinding, entity_id):
            skipped += 1
            continue
        db.add(
            WorkflowBinding(
                id=entity_id,
                portal_account_id=item["portalAccountId"],
                workflow_template_id=item["workflowTemplateId"],
                workflow_template_version=item.get("workflowTemplateVersion", "1.0.0"),
                rpa_engine_type=item.get("rpaEngineType", "PLAYWRIGHT_CDP"),
                rpa_flow_id=item["rpaFlowId"],
                rpa_flow_version=item.get("rpaFlowVersion", "1.0.0"),
                rpa_flow_version_id=item.get("rpaFlowVersionId"),
                flow_checksum_snapshot=item.get("flowChecksumSnapshot"),
                status=item.get("status", "ENABLED"),
                config=dumps_json(item.get("config", {})),
                created_by=item.get("createdBy", DEFAULT_USER_ID),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_tasks(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("tasks.json"):
        entity_id = item.get("id")
        if await _exists_by_id(db, AutomationTask, entity_id):
            skipped += 1
            continue
        db.add(
            AutomationTask(
                id=entity_id,
                tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                title=item["title"],
                task_type=item["taskType"],
                portal_account_id=item["portalAccountId"],
                workflow_binding_id=item["workflowBindingId"],
                entity_type=item["entityType"],
                erp_entity_code=item["erpEntityCode"],
                erp_entity_name=item["erpEntityName"],
                status=item.get("status", "DRAFT"),
                priority=item.get("priority", "NORMAL"),
                input=dumps_json(item.get("input", {})),
                current_step=item.get("currentStep"),
                progress=item.get("progress", 0),
                created_by=item.get("createdBy", DEFAULT_USER_ID),
                assigned_to=item.get("assignedTo"),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_task_runs(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    runs_data = _load_json("task-runs.json")
    if not isinstance(runs_data, dict):
        return 0, 0

    for item in runs_data.get("runs", []):
        entity_id = item.get("id")
        if await _exists_by_id(db, RpaRun, entity_id):
            skipped += 1
            continue
        db.add(
            RpaRun(
                id=entity_id,
                task_id=item["taskId"],
                rpa_flow_id=item["rpaFlowId"],
                rpa_worker_id=item.get("rpaWorkerId"),
                lease_id=item.get("leaseId"),
                status=item.get("status", "QUEUED"),
                current_step_id=item.get("currentStepId"),
            )
        )
        inserted += 1

    for item in runs_data.get("stepRuns", []):
        entity_id = item.get("id")
        if await _exists_by_id(db, StepRun, entity_id):
            skipped += 1
            continue
        db.add(
            StepRun(
                id=entity_id,
                run_id=item["runId"],
                step_id=item["stepId"],
                step_name=item.get("stepName", ""),
                status=item.get("status", "PENDING"),
                output=dumps_json(item.get("output", {})),
            )
        )
        inserted += 1

    for item in runs_data.get("events", []):
        entity_id = item.get("id")
        if await _exists_by_id(db, RunEvent, entity_id):
            skipped += 1
            continue
        db.add(
            RunEvent(
                id=entity_id,
                run_id=item["runId"],
                task_id=item["taskId"],
                worker_id=item.get("workerId"),
                type=item["type"],
                level=item.get("level", "INFO"),
                message=item["message"],
                payload=dumps_json(item.get("payload", {})),
            )
        )
        inserted += 1

    return inserted, skipped


async def _seed_workers(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("workers.json"):
        worker_id = item["id"]
        existing = (
            await db.execute(
                select(RpaWorker.id).where(RpaWorker.worker_id == worker_id).limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        db.add(
            RpaWorker(
                worker_id=worker_id,
                worker_type=item["workerType"],
                device_name=item["deviceName"],
                user_id=item.get("userId"),
                status=item.get("status", "ONLINE"),
                capabilities=dumps_json(item.get("capabilities", [])),
                app_version=item.get("appVersion"),
                agent_version=item.get("agentVersion"),
                os=item.get("os"),
                current_run_id=item.get("currentRunId"),
                last_heartbeat_at=datetime.now(UTC),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_artifacts(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("artifacts.json"):
        entity_id = item.get("id")
        if await _exists_by_id(db, Artifact, entity_id):
            skipped += 1
            continue
        db.add(
            Artifact(
                id=entity_id,
                tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                task_id=item["taskId"],
                run_id=item.get("runId"),
                type=item["type"],
                name=item["name"],
                storage_key=item["storageKey"],
                size=item.get("size", 0),
                mime_type=item.get("mimeType"),
                created_by=item.get("createdBy"),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_components(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("rpa-components.json"):
        entity_id = item.get("id")
        if await _exists_by_id(db, RpaComponent, entity_id):
            skipped += 1
            continue
        db.add(
            RpaComponent(
                id=entity_id,
                name=item["name"],
                type=item["type"],
                config=dumps_json(item.get("config", {})),
                description=item.get("description"),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_settings(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    settings_data = _load_json("settings.json")
    if not isinstance(settings_data, dict):
        return 0, 0
    for key, value in settings_data.items():
        existing = (
            await db.execute(
                select(AutotaskSetting.id).where(
                    AutotaskSetting.tenant_id == DEFAULT_TENANT_ID,
                    AutotaskSetting.key == key,
                    not_deleted(AutotaskSetting),
                ).limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        db.add(
            AutotaskSetting(
                tenant_id=DEFAULT_TENANT_ID,
                key=key,
                value=dumps_json(value),
            )
        )
        inserted += 1
    return inserted, skipped


async def _seed_audit_logs(db: AsyncSession) -> tuple[int, int]:
    inserted = skipped = 0
    for item in _load_json("audit-logs.json"):
        entity_id = item.get("id")
        if await _exists_by_id(db, AuditLog, entity_id):
            skipped += 1
            continue
        db.add(
            AuditLog(
                id=entity_id,
                tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                actor_id=item.get("actorId", DEFAULT_USER_ID),
                action=item["action"],
                resource_type=item["resourceType"],
                resource_id=item["resourceId"],
                details=dumps_json(item.get("details", {})),
            )
        )
        inserted += 1
    return inserted, skipped


async def run_seed(session_factory: async_sessionmaker) -> None:
    """Idempotent seed: fill missing rows by id; skip groups when schema is broken."""
    groups: list[tuple[str, Callable[[AsyncSession], Awaitable[tuple[int, int]]]]] = [
        ("portal_accounts", _seed_portal_accounts),
        ("portal_access_grants", _seed_portal_access_grants),
        ("workflow_templates", _seed_workflow_templates),
        ("workflow_bindings", _seed_workflow_bindings),
        ("automation_tasks", _seed_tasks),
        ("task_runs", _seed_task_runs),
        ("rpa_workers", _seed_workers),
        ("artifacts", _seed_artifacts),
        ("rpa_components", _seed_components),
        ("autotask_settings", _seed_settings),
        ("audit_logs", _seed_audit_logs),
    ]

    total_inserted = total_skipped = 0
    async with session_factory() as db:
        for group_name, seed_fn in groups:
            inserted, skipped = await _seed_group(db, group_name, lambda fn=seed_fn: fn(db))
            total_inserted += inserted
            total_skipped += skipped

        try:
            await db.commit()
        except _SEED_SKIP_ERRORS as exc:
            await db.rollback()
            logger.warning(
                "种子数据提交失败（已回滚，不影响服务启动）。原因: %s",
                exc,
            )
            return

    logger.info(
        "种子数据同步完成：新增 %s，已存在跳过 %s",
        total_inserted,
        total_skipped,
    )
