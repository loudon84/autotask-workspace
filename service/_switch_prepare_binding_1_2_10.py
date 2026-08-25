"""Switch srm_prepare_erp_order binding from 1.2.9 to 1.2.10 for 天地伟业 portals."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.deps import async_session_factory
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.rpa_engine_client import normalize_checksum

PUBLISH = Path(r"d:\work_space260811\autotask-workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\_publish_1.2.10.json")


async def main() -> None:
    published = json.loads(PUBLISH.read_text(encoding="utf-8"))
    flow_version = published["rpaFlowVersion"]
    flow_version_id = published["rpaFlowVersionId"]
    checksum = normalize_checksum(published["packageChecksum"]) or ""
    print(f"target: {flow_version} ({flow_version_id}) checksum={checksum[:12]}...")

    async with async_session_factory() as db:
        portals = (
            await db.execute(
                select(PortalAccount.id, PortalAccount.portal_name).where(
                    PortalAccount.portal_name.like("天地伟业%")
                )
            )
        ).all()
        portal_ids = {p.id: p.portal_name for p in portals}
        print(f"portals: {list(portal_ids.values())}")

        bindings = (
            await db.execute(
                select(WorkflowBinding)
                .join(WorkflowTemplate, WorkflowTemplate.id == WorkflowBinding.workflow_template_id)
                .where(
                    WorkflowTemplate.code == "srm_prepare_erp_order",
                    not_deleted(WorkflowTemplate),
                    WorkflowBinding.portal_account_id.in_(list(portal_ids.keys())),
                    not_deleted(WorkflowBinding),
                )
            )
        ).scalars().all()
        print(f"bindings found: {len(bindings)}")
        for b in bindings:
            name = portal_ids.get(b.portal_account_id, "?")
            print(f"  {name}: {b.rpa_flow_id}@{b.rpa_flow_version} -> {flow_version}")
            b.rpa_flow_version = flow_version
            b.rpa_flow_version_id = flow_version_id
            b.flow_checksum_snapshot = checksum
            b.status = "ENABLED"
        await db.commit()
        print("committed")


if __name__ == "__main__":
    asyncio.run(main())
