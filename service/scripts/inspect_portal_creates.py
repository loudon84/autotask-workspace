# -*- coding: utf-8 -*-
"""只读：列出所有 portal_account.created 审计记录的时间/actor，并对比 created vs updated 的校验差异。"""
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
        creates = (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.action == "portal_account.created", not_deleted(AuditLog))
                .order_by(AuditLog.created_at.desc())
            )
        ).scalars().all()
        print("=== portal_account.created 记录 ===")
        for a in creates:
            print(
                f"{a.created_at} actor={a.actor_id} ({users.get(a.actor_id, '?')}) "
                f"resource={a.resource_id} details={a.details[:100]}"
            )
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
