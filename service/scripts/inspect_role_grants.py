# -*- coding: utf-8 -*-
"""只读：按 subject_type/subject_id 汇总 portal_access_grants 的权限，看各角色实际能做什么。"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.portal_access_grant import PortalAccessGrant
from app.models.portal_account import PortalAccount


async def main() -> int:
    async with async_session_factory() as db:
        portals = {p.id: p.portal_name for p in (
            await db.execute(select(PortalAccount).where(not_deleted(PortalAccount)))
        ).scalars().all()}
        grants = (
            await db.execute(select(PortalAccessGrant).where(not_deleted(PortalAccessGrant)))
        ).scalars().all()
        by_subject: dict[tuple[str, str], list[tuple[str, list[str]]]] = defaultdict(list)
        for g in grants:
            try:
                perms = json.loads(g.permissions or "[]")
            except json.JSONDecodeError:
                perms = []
            by_subject[(g.subject_type, g.subject_id)].append(
                (portals.get(g.portal_account_id, g.portal_account_id), perms)
            )
        print("=== 各角色/主体当前被授予的权限 ===")
        for (stype, sid), entries in sorted(by_subject.items()):
            print(f"\n[{stype}={sid}] 共 {len(entries)} 条")
            # 汇总该主体出现过的权限并集
            union: set[str] = set()
            for _portal, perms in entries:
                union.update(perms)
            print(f"  权限并集: {sorted(union)}")
            for portal, perms in entries[:5]:
                print(f"  - 门户 {portal}: {perms}")
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
