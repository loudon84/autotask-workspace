# -*- coding: utf-8 -*-
"""只读查看 POJS2607240005 实例当前阶段/错误/归档子任务状态。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.services.json_utils import loads_json
from app.services.process_instance_service import (
    ARCHIVE_TEMPLATE_CODE,
    CHECK_REPLY_TEMPLATE_CODE,
    PROCESS_CODE_SRM_CUSTOMER_ORDER,
)

PO_NO = "POJS2607240005"
PORTAL_NAME = "天地伟业-国际test"


async def main() -> int:
    async with async_session_factory() as db:
        portal = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == PORTAL_NAME,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
        instance = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.portal_account_id == portal.id,
                    ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
                    ProcessInstance.biz_key == PO_NO,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one_or_none()
        print(f"instance id={instance.id}")
        print(f"  stage={instance.stage} status={instance.status}")
        print(f"  error_code={instance.last_error_code} error_message={instance.last_error_message}")
        summary = loads_json(instance.summary, {})
        print(f"  summary.sdmsUsername={summary.get('sdmsUsername')!r}")

        tasks = (
            await db.execute(
                select(AutomationTask).where(
                    AutomationTask.process_instance_id == instance.id,
                    not_deleted(AutomationTask),
                )
            )
        ).scalars().all()
        for t in tasks:
            print(
                f"  task id={t.id} type={t.task_type} status={t.status} "
                f"title={t.title}"
            )
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
