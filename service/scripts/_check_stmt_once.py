"""One-off check of latest submit task. Do not commit."""
import asyncio
import json
from pathlib import Path

url = None
env_path = Path(__file__).resolve().parents[1] / ".env.product"
for line in env_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        url = line.split("=", 1)[1].strip()
url = url.replace("postgresql+asyncpg://", "postgresql://")

import asyncpg

INSTANCE_ID = "fb777fff-d2df-4f5f-b5b5-22635e9d89cd"


async def main() -> None:
    conn = await asyncpg.connect(url)
    try:
        bill = await conn.fetchrow(
            "SELECT check_status, invoice_status, last_error, updated_at FROM statement_bills WHERE process_instance_id = $1",
            INSTANCE_ID,
        )
        inst = await conn.fetchrow(
            "SELECT status, stage, last_error_code, last_error_message, updated_at FROM process_instances WHERE id = $1",
            INSTANCE_ID,
        )
        print("bill:", dict(bill))
        print("inst:", dict(inst))

        tasks = await conn.fetch(
            """
            SELECT id, task_type, status, title, created_at, updated_at
            FROM automation_tasks
            WHERE process_instance_id = $1
            ORDER BY created_at DESC
            LIMIT 3
            """,
            INSTANCE_ID,
        )
        for task in tasks:
            print("\ntask:", json.dumps({k: (None if task[k] is None else str(task[k])) for k in task.keys()}, ensure_ascii=False))
            runs = await conn.fetch(
                """
                SELECT id, status, error_code, error_message, started_at, ended_at, output
                FROM rpa_runs
                WHERE task_id = $1
                ORDER BY created_at DESC
                LIMIT 2
                """,
                task["id"],
            )
            for run in runs:
                output = run["output"]
                if isinstance(output, str):
                    try:
                        output = json.loads(output)
                    except json.JSONDecodeError:
                        pass
                keep = None
                if isinstance(output, dict):
                    keep = {k: output.get(k) for k in (
                        "committed", "dryRun", "blockedAction", "checkDate", "checkAmount",
                        "invoiceNo", "invoiceAmount", "submitButtonFound", "message", "ok",
                        "error", "reason",
                    ) if k in output}
                print("  run:", json.dumps({
                    "id": str(run["id"]),
                    "status": run["status"],
                    "error": run["error_message"],
                    "started": None if run["started_at"] is None else str(run["started_at"]),
                    "ended": None if run["ended_at"] is None else str(run["ended_at"]),
                    "output": keep if keep is not None else str(output)[:600],
                }, ensure_ascii=False))
    finally:
        await conn.close()


asyncio.run(main())
