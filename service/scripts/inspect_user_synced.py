# -*- coding: utf-8 -*-
"""只读查 user_cache synced_at，判断角色是后端改的还是缓存陈旧。"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.user_cache import UserCache


async def main() -> int:
    async with async_session_factory() as db:
        users = (
            await db.execute(select(UserCache).where(not_deleted(UserCache)))
        ).scalars().all()
        now = datetime.now(UTC)
        for u in users:
            synced = u.synced_at if u.synced_at.tzinfo else u.synced_at.replace(tzinfo=UTC)
            age_min = (now - synced).total_seconds() / 60
            print(
                f"{u.name}: org_role={u.org_role!r} portal_org_role={u.portal_org_role!r} "
                f"super_admin={u.is_super_admin} synced_at={u.synced_at} (age {age_min:.0f}min)"
            )
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
