"""Queue missing 建 SDMS sub-tasks for official-portal instances stuck in CREATING_SDMS."""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.enums import ProcessInstanceStatus, ProcessStage
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.services import process_instance_service as svc

OFFICIAL_PORTAL_NAME = "天地伟业-国际-正式演练"


async def main() -> None:
    async with async_session_factory() as db:
        official = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == OFFICIAL_PORTAL_NAME,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one()
        instances = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.portal_account_id == official.id,
                    ProcessInstance.stage == ProcessStage.CREATING_SDMS.value,
                    ProcessInstance.status == ProcessInstanceStatus.ACTIVE.value,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalars().all()
        print("stuck", len(instances))
        for instance in instances:
            print("instance", instance.id, instance.biz_key, instance.stage)
            task = await svc._ensure_prepare_sub_task(
                db,
                instance,
                actor=instance.created_by,
                allow_missing_prepare_binding=False,
            )
            if task is None:
                print("  skipped (already has prepare task)")
            else:
                print("  queued", task.id, task.title)
        await db.commit()
    await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
