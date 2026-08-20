# -*- coding: utf-8 -*-
"""只读：打印指定门户的完整字段 + 其所有 WorkflowBinding 概况。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate

PORTAL_NAME = "天地伟业-国际-正式演练"


async def main() -> int:
    async with async_session_factory() as db:
        portal = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == PORTAL_NAME, not_deleted(PortalAccount)
                )
            )
        ).scalar_one_or_none()
        if portal is None:
            print(f"找不到门户 {PORTAL_NAME}")
            await db_engine.dispose()
            return 1
        print("=== 门户字段 ===")
        for c in portal.__table__.columns:
            v = getattr(portal, c.name)
            if c.name == "credential_ref":
                v = ("<set>" if v else "<empty>")
            print(f"  {c.name} = {v!r}")

        print("\n=== 该门户的 WorkflowBinding ===")
        rows = (
            await db.execute(
                select(WorkflowBinding, WorkflowTemplate)
                .join(WorkflowTemplate, WorkflowTemplate.id == WorkflowBinding.workflow_template_id)
                .where(WorkflowBinding.portal_account_id == portal.id, not_deleted(WorkflowBinding))
            )
        ).all()
        if not rows:
            print("  （无绑定）")
        for b, t in rows:
            cfg = {}
            try:
                cfg = json.loads(b.config or "{}")
            except json.JSONDecodeError:
                pass
            print(
                f"  - template={t.code} binding_status={b.status} "
                f"flow={b.rpa_flow_id}@{b.rpa_flow_version} "
                f"dryRun={cfg.get('dryRun', '<未设>')} portalUrl={cfg.get('portalUrl', '<未设>')}"
            )
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
