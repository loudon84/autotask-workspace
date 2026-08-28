# -*- coding: utf-8 -*-
"""Create schema rpa_engine on the Engine DATABASE_URL database."""
from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

ENV = Path(__file__).resolve().parents[1] / ".env"


def load_dsn() -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            raw = line.split("=", 1)[1].strip().strip('"').strip("'")
            return raw.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("no DATABASE_URL")


async def main() -> None:
    dsn = load_dsn()
    parsed = urlparse(dsn)
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        db = await conn.fetchval("SELECT current_database()")
        await conn.execute("CREATE SCHEMA IF NOT EXISTS rpa_engine")
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.schemata
              WHERE schema_name = 'rpa_engine'
            )
            """
        )
        print(f"host={parsed.hostname} db={db} schema_rpa_engine={exists}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
