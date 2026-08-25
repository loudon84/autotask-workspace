# -*- coding: utf-8 -*-
"""只读列出 user_cache 用户及其角色，定位创建门户权限问题。"""
from __future__ import annotations

import asyncio
import sys
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
        for u in users:
            print(
                f"user_id={u.user_id} name={u.name} "
                f"org={u.current_org_id} org_role={u.org_role!r} "
                f"portal_org_role={u.portal_org_role!r} "
                f"super_admin={u.is_super_admin}"
            )
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
