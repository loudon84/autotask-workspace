# -*- coding: utf-8 -*-
"""只读查 audit_logs 里门户创建记录，确认测试门户是 UI 建的还是脚本建的。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.audit_log import AuditLog
from app.models.base import not_deleted
from app.models.user_cache import UserCache


async def main() -> int:
    async with async_session_factory() as db:
        users = {u.user_id: u.name for u in (
            await db.execute(select(UserCache).where(not_deleted(UserCache)))
        ).scalars().all()}
        logs = (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.resource_type == "portal_account", not_deleted(AuditLog))
                .order_by(AuditLog.created_at.desc())
            )
        ).scalars().all()
        for a in logs[:30]:
            print(
                f"{a.created_at} actor={a.actor_id} ({users.get(a.actor_id, '?')}) "
                f"action={a.action} resource={a.resource_id} "
                f"details={a.details[:120]}"
            )
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
