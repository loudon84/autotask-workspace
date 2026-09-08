"""临时：查最近一次京东方 enrich Run 及产物。用完即删。"""

import asyncio

from sqlalchemy import select

from app.core.deps import async_session_factory
from app.models.artifact import Artifact
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.rpa_run import RpaRun


async def main() -> None:
    async with async_session_factory() as db:
        task = (
            await db.execute(
                select(AutomationTask)
                .where(
                    AutomationTask.task_type == "srm_boe_pack_enrich",
                    not_deleted(AutomationTask),
                )
                .order_by(AutomationTask.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if task is None:
            print("no enrich task")
            return
        print(f"task id={task.id} status={task.status} created={task.created_at}")
        runs = (
            (
                await db.execute(
                    select(RpaRun)
                    .where(RpaRun.task_id == task.id, not_deleted(RpaRun))
                    .order_by(RpaRun.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        for run in runs:
            print(f"run id={run.id} status={run.status} error={run.error_code} {run.error_message}")
            arts = (
                (
                    await db.execute(
                        select(Artifact).where(
                            Artifact.run_id == run.id, not_deleted(Artifact)
                        )
                    )
                )
                .scalars()
                .all()
            )
            for a in arts:
                print(f"  artifact {a.name} type={a.type} key={a.storage_key}")


asyncio.run(main())
