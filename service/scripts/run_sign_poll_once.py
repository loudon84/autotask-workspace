# -*- coding: utf-8 -*-
"""手动触发一次回签轮询（等价于点「立即回签轮询」按钮）。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.core.deps import async_session_factory, engine as db_engine
from app.services.process_instance_service import run_sign_poll_once


async def main() -> int:
    async with async_session_factory() as db:
        result = await run_sign_poll_once(db, actor="scripts/run_sign_poll_once")
        await db.commit()
        print(result)
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
