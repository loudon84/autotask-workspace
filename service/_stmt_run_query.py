"""Create a read-only receipt query task and wait for Worker result."""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.core.deps import async_session_factory
from app.models.automation_task import AutomationTask
from app.models.rpa_run import RpaRun
from app.services import statement_service

TENANT_ID = "2be7c618-326d-4a73-91ea-1cfda10f7073"
PORTAL_ID = "b182630d-5023-45c3-ac9c-6b022765b7e1"
ACTOR_ID = "8468ef67-e4d6-4efd-bc41-ca5189449b09"


async def main() -> int:
    async with async_session_factory() as db:
        task = await statement_service.query_receipts(
            db,
            TENANT_ID,
            PORTAL_ID,
            "2026-04-01",
            "2026-04-30",
            actor=ACTOR_ID,
        )
        task_id = task.id
        print("created", task_id, task.status)
    for _ in range(40):
        await asyncio.sleep(3)
        async with async_session_factory() as db:
            task = (
                await db.execute(select(AutomationTask).where(AutomationTask.id == task_id))
            ).scalar_one()
            run = (
                await db.execute(
                    select(RpaRun)
                    .where(RpaRun.task_id == task_id)
                    .order_by(RpaRun.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            run_status = run.status if run else None
            error = (run.error_code if run else None, run.error_message if run else None)
            print("poll", task.status, run_status, error[0])
            if task.status in {"SUCCESS", "FAILED", "WAITING_HUMAN"} or (
                run_status in {"SUCCESS", "FAILED", "WAITING_HUMAN"}
            ):
                output = run.output if run else None
                if isinstance(output, dict):
                    print("rows", output.get("totalRows"), "status", output.get("schemaVersion"))
                    rows = output.get("rows") or []
                    if rows:
                        print("first", json.dumps(rows[0], ensure_ascii=False))
                else:
                    print("output", output)
                    print("error", error)
                return 0 if task.status == "SUCCESS" or run_status == "SUCCESS" else 1
    print("timeout")
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
