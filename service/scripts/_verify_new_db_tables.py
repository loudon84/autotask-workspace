# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

ENV = Path(__file__).resolve().parents[1] / ".env"
NEED = [
    "automation_tasks",
    "workflow_bindings",
    "portal_accounts",
    "process_instances",
    "statement_bills",
    "scheduler_jobs",
    "integration_call_logs",
    "autotask_user_cache",
]


def load_dsn() -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            raw = line.split("=", 1)[1].strip().strip('"').strip("'")
            return raw.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("no DATABASE_URL")


async def main() -> None:
    conn = await asyncpg.connect(load_dsn(), statement_cache_size=0)
    try:
        db = await conn.fetchval("SELECT current_database()")
        ver = await conn.fetchval("SELECT version_num FROM alembic_version")
        names = {
            r["table_name"]
            for r in await conn.fetch(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """
            )
        }
        print(f"db={db} alembic={ver} public_tables={len(names)}")
        for table in NEED:
            print(("OK" if table in names else "MISSING"), table)
        admin = await conn.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_name = 'autotask_user_cache'
                AND column_name = 'is_task_admin'
            )
            """
        )
        print(f"is_task_admin={admin}")
        engine_names = {
            r["table_name"]
            for r in await conn.fetch(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'rpa_engine' AND table_type = 'BASE TABLE'
                """
            )
        }
        print(f"rpa_engine_tables={len(engine_names)}")
        for table in (
            "rpa_flows",
            "rpa_flow_versions",
            "rpa_worker_instances",
        ):
            print(("OK" if table in engine_names else "MISSING"), f"rpa_engine.{table}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
