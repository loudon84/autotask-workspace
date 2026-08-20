# -*- coding: utf-8 -*-
"""只读列出门户及其 created_by，定位当前操作者。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache


async def main() -> int:
    async with async_session_factory() as db:
        users = {u.user_id: u.name for u in (
            await db.execute(select(UserCache).where(not_deleted(UserCache)))
        ).scalars().all()}
        portals = (
            await db.execute(select(PortalAccount).where(not_deleted(PortalAccount)))
        ).scalars().all()
        for p in portals:
            print(
                f"portal={p.portal_name} created_by={p.created_by} "
                f"({users.get(p.created_by, '?')}) status={p.status}"
            )
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
