# -*- coding: utf-8 -*-
"""Empty-DB bootstrap: initial Alembic revision is metadata.create_all.

Later revisions then conflict. On a new database, create current models and
leave alembic_version at head (already stamped).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.core.config import settings
from app.models import Base


async def main() -> None:
    safe = settings.DATABASE_URL.split("@")[-1]
    print(f"create_all target {safe}")
    engine = create_async_engine(settings.DATABASE_URL, connect_args={"ssl": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("create_all done")


if __name__ == "__main__":
    asyncio.run(main())
