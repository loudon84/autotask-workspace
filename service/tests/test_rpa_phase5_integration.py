"""Phase 5 DB integration: lease concurrency and snapshot reuse."""

import os
import uuid

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")
os.environ.setdefault("RPA_ENGINE_VALIDATE_BINDING", "false")
os.environ.setdefault("ARTIFACT_STORAGE", "local")

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import RunEventType, TaskStatus, WorkerStatus
from app.models.portal_account import PortalAccount
from app.models.rpa_run import RpaRun
from app.models.rpa_worker import RpaWorker
from app.models.step_run import StepRun
from app.models.worker_lease import WorkerLease
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.schemas.dispatch import RunEventCreate, WorkerLeaseRenewRequest, WorkerLeaseRequest
from app.services import dispatch_service
from app.services.json_utils import dumps_json


@pytest.fixture
async def db_factory():
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        connect_args={"ssl": False},
        pool_size=5,
        max_overflow=0,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _cleanup(factory, prefix: str) -> None:
    async with factory() as db:
        tasks = (await db.execute(select(AutomationTask).where(AutomationTask.id.like(f"{prefix}%")))).scalars().all()
        task_ids = [t.id for t in tasks]
        runs = []
        if task_ids:
            runs = (await db.execute(select(RpaRun).where(RpaRun.task_id.in_(task_ids)))).scalars().all()
        run_ids = [r.id for r in runs]
        if run_ids:
            steps = (await db.execute(select(StepRun).where(StepRun.run_id.in_(run_ids)))).scalars().all()
            for step in steps:
                step.soft_delete()
            leases = (await db.execute(select(WorkerLease).where(WorkerLease.run_id.in_(run_ids)))).scalars().all()
            for lease in leases:
                lease.soft_delete()
            for run in runs:
                run.soft_delete()
        for task in tasks:
            task.soft_delete()
        for model in (WorkflowBinding, WorkflowTemplate, PortalAccount):
            rows = (await db.execute(select(model).where(model.id.like(f"{prefix}%")))).scalars().all()
            for row in rows:
                row.soft_delete()
        workers = (
            await db.execute(select(RpaWorker).where(RpaWorker.worker_id.like(f"{prefix}%")))
        ).scalars().all()
        for w in workers:
            w.soft_delete()
        await db.commit()


async def _seed_binding_graph(db, prefix: str) -> tuple[str, str, str]:
    tenant_id = f"{prefix}-tenant"
    portal_id = f"{prefix}-portal"
    template_id = f"{prefix}-tpl"
    binding_id = f"{prefix}-binding"
    task_id = f"{prefix}-task"

    db.add(
        PortalAccount(
            id=portal_id,
            tenant_id=tenant_id,
            entity_type="CUSTOMER",
            erp_entity_code="CUST",
            erp_entity_name="客户",
            portal_name="Mock SRM",
            portal_url="https://portal.example.com/srm",
            login_account="buyer@example.com",
            credential_ref="credential-ref-mock-srm",
            status="ENABLED",
            created_by="tester",
        )
    )
    db.add(
        WorkflowTemplate(
            id=template_id,
            tenant_id=tenant_id,
            name="SRM fetch",
            code="srm_fetch_po",
            entity_type="CUSTOMER",
            status="ENABLED",
            version="1.0.0",
            input_schema="[]",
            business_steps="[]",
            created_by="tester",
        )
    )
    db.add(
        WorkflowBinding(
            id=binding_id,
            portal_account_id=portal_id,
            workflow_template_id=template_id,
            workflow_template_version="1.0.0",
            rpa_engine_type="PLAYWRIGHT_CDP",
            rpa_flow_id="rpa_flow_mock_srm_fetch_po",
            rpa_flow_version="1.0.0",
            rpa_flow_version_id="flow-version-1",
            flow_checksum_snapshot="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            status="ENABLED",
            config=dumps_json(
                {
                    "browserSession": {
                        "mode": "MANAGED",
                        "headless": True,
                        "channel": "chrome",
                        "closePolicy": "CLOSE_ON_FINISH",
                    }
                }
            ),
            created_by="tester",
        )
    )
    db.add(
        AutomationTask(
            id=task_id,
            tenant_id=tenant_id,
            title="phase5",
            task_type="srm_fetch_po",
            portal_account_id=portal_id,
            workflow_binding_id=binding_id,
            entity_type="CUSTOMER",
            erp_entity_code="CUST",
            erp_entity_name="客户",
            status=TaskStatus.QUEUED,
            input=dumps_json({"po_no": "PO-20260708-001"}),
            created_by="tester",
        )
    )
    return binding_id, task_id, portal_id


@pytest.mark.asyncio
async def test_lease_snapshot_and_renew_and_step_projection(db_factory):
    prefix = f"p5-{uuid.uuid4().hex[:8]}"
    worker_id = f"{prefix}-worker"

    try:
        async with db_factory() as db:
            _, task_id, _ = await _seed_binding_graph(db, prefix)
            db.add(
                RpaWorker(
                    worker_id=worker_id,
                    worker_type="SERVER_WORKER",
                    device_name="test-worker",
                    status=WorkerStatus.ONLINE,
                    capabilities=dumps_json(["PLAYWRIGHT_CDP", "BROWSER_SESSION_MANAGED"]),
                    last_heartbeat_at=datetime.now(UTC),
                )
            )
            await db.commit()

        async with db_factory() as db:
            lease = await dispatch_service.lease_task(
                db,
                WorkerLeaseRequest(worker_id=worker_id, capabilities=["PLAYWRIGHT_CDP"], limit=1),
            )
            assert lease is not None
            assert lease.workflow_code == "srm_fetch_po"
            assert lease.credential_ref == "credential-ref-mock-srm"
            assert lease.config.portal_url == "https://portal.example.com/srm"
            assert lease.input == {"po_no": "PO-20260708-001"}
            run_id = lease.run_id
            lease_id = lease.lease_id
            original_portal = lease.config.portal_url
            binding_id = lease.workflow_binding_id

        async with db_factory() as db:
            binding = (
                await db.execute(select(WorkflowBinding).where(WorkflowBinding.id == binding_id))
            ).scalar_one()
            binding.config = dumps_json(
                {
                    "portalUrl": "https://portal.example.com/srm-changed",
                    "browserSession": {"mode": "MANAGED", "channel": "chrome", "closePolicy": "CLOSE_ON_FINISH"},
                }
            )
            await db.commit()

        async with db_factory() as db:
            renewed = await dispatch_service.renew_lease(
                db,
                task_id,
                WorkerLeaseRenewRequest(worker_id=worker_id, lease_id=lease_id),
            )
            assert renewed.lease_expires_at.tzinfo is not None

        async with db_factory() as db:
            await dispatch_service.append_run_event(
                db,
                run_id,
                RunEventCreate(
                    worker_id=worker_id,
                    type=RunEventType.STEP_STARTED,
                    level="INFO",
                    message="Searching",
                    payload={"stepId": "srm.search_po"},
                ),
            )
            step = (
                await db.execute(
                    select(StepRun).where(
                        StepRun.run_id == run_id,
                        StepRun.step_id == "srm.search_po",
                        not_deleted(StepRun),
                    )
                )
            ).scalar_one()
            assert step.status == "RUNNING"
            assert step.step_name == "srm.search_po"

            await dispatch_service.append_run_event(
                db,
                run_id,
                RunEventCreate(
                    worker_id=worker_id,
                    type=RunEventType.STEP_WAITING_HUMAN,
                    message="Need human",
                    payload={"stepId": "srm.search_po", "stepName": "搜索采购订单"},
                ),
            )
            step = (
                await db.execute(
                    select(StepRun).where(
                        StepRun.run_id == run_id,
                        StepRun.step_id == "srm.search_po",
                        not_deleted(StepRun),
                    )
                )
            ).scalar_one()
            assert step.status == "WAITING_HUMAN"
            assert step.step_name == "搜索采购订单"

        async with db_factory() as db:
            run_row = (await db.execute(select(RpaRun).where(RpaRun.id == run_id))).scalar_one()
            assert run_row.command_snapshot["config"]["portalUrl"] == original_portal

            wl = (
                await db.execute(
                    select(WorkerLease).where(
                        WorkerLease.lease_id == lease_id,
                        not_deleted(WorkerLease),
                    )
                )
            ).scalar_one()
            wl.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()

        async with db_factory() as db:
            re_lease = await dispatch_service.lease_task(
                db,
                WorkerLeaseRequest(worker_id=worker_id, capabilities=["PLAYWRIGHT_CDP"], limit=1),
            )
            assert re_lease is not None
            assert re_lease.run_id == run_id
            assert re_lease.lease_id != lease_id
            assert re_lease.config.portal_url == original_portal
    finally:
        await _cleanup(db_factory, prefix)


@pytest.mark.asyncio
async def test_two_workers_only_one_leases_same_task(db_factory):
    prefix = f"p5c-{uuid.uuid4().hex[:8]}"
    w1 = f"{prefix}-w1"
    w2 = f"{prefix}-w2"

    try:
        async with db_factory() as db:
            _, task_id, _ = await _seed_binding_graph(db, prefix)
            for wid in (w1, w2):
                db.add(
                    RpaWorker(
                        worker_id=wid,
                        worker_type="SERVER_WORKER",
                        device_name=wid,
                        status=WorkerStatus.ONLINE,
                        capabilities=dumps_json(["PLAYWRIGHT_CDP"]),
                        last_heartbeat_at=datetime.now(UTC),
                    )
                )
            await db.commit()

        async with db_factory() as db:
            first = await dispatch_service.lease_task(
                db,
                WorkerLeaseRequest(worker_id=w1, capabilities=["PLAYWRIGHT_CDP"], limit=1),
            )
        async with db_factory() as db:
            second = await dispatch_service.lease_task(
                db,
                WorkerLeaseRequest(worker_id=w2, capabilities=["PLAYWRIGHT_CDP"], limit=1),
            )
        leased = [r for r in (first, second) if r is not None]
        assert len(leased) == 1
        assert leased[0].task_id == task_id
    finally:
        await _cleanup(db_factory, prefix)
