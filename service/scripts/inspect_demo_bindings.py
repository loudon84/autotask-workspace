# -*- coding: utf-8 -*-
"""只读：列出指定门户的所有绑定 + 各 workflow 模板，便于克隆到正式门户。"""
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

PORTAL_NAME = "天地伟业-国际test"


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
        rows = (
            await db.execute(
                select(WorkflowBinding, WorkflowTemplate)
                .join(WorkflowTemplate, WorkflowTemplate.id == WorkflowBinding.workflow_template_id)
                .where(WorkflowBinding.portal_account_id == portal.id, not_deleted(WorkflowBinding))
                .order_by(WorkflowTemplate.code)
            )
        ).all()
        print(f"=== {PORTAL_NAME} 的 {len(rows)} 条绑定 ===")
        for b, t in rows:
            cfg = {}
            try:
                cfg = json.loads(b.config or "{}")
            except json.JSONDecodeError:
                pass
            print(
                f"\n  template_code = {t.code}"
                f"\n    template_name = {t.name}"
                f"\n    binding_id = {b.id}  status = {b.status}"
                f"\n    flow = {b.rpa_flow_id} @ {b.rpa_flow_version}"
                f"\n    flow_version_id = {b.rpa_flow_version_id}"
                f"\n    config = {json.dumps(cfg, ensure_ascii=False)}"
            )
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
