"""Switch demo-portal scan bindings to 1.0.2 OCR. Does not touch the official portal."""
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

PUBLISH = Path(
    r"d:\work_space260811\autotask-workspace\rpa-flows\rpa_flow_srm_scan_pending_orders\_publish_1.0.2.json"
)
DEMO_HOST = "192.168.102.247"
OFFICIAL_URL = "supplier.tiandy.com"


async def main() -> None:
    published = json.loads(PUBLISH.read_text(encoding="utf-8"))
    version = published["rpaFlowVersion"]
    version_id = published["rpaFlowVersionId"]
    checksum = normalize_checksum(published["packageChecksum"]) or ""
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(WorkflowBinding, PortalAccount, WorkflowTemplate)
                .join(PortalAccount, PortalAccount.id == WorkflowBinding.portal_account_id)
                .join(
                    WorkflowTemplate,
                    WorkflowTemplate.id == WorkflowBinding.workflow_template_id,
                )
                .where(
                    WorkflowTemplate.code == "srm_scan_pending_orders",
                    not_deleted(WorkflowBinding),
                    not_deleted(PortalAccount),
                    not_deleted(WorkflowTemplate),
                )
            )
        ).all()
        for binding, portal, _template in rows:
            url = portal.portal_url or ""
            if OFFICIAL_URL in url:
                print("skip_official", portal.portal_name, binding.rpa_flow_version)
                continue
            if DEMO_HOST not in url:
                print("skip_other", portal.portal_name, url)
                continue
            print(
                "switch",
                portal.portal_name,
                binding.rpa_flow_version,
                "->",
                version,
            )
            binding.rpa_flow_version = version
            binding.rpa_flow_version_id = version_id
            binding.flow_checksum_snapshot = checksum
            binding.status = "ENABLED"
        await db.commit()
        print("committed")


if __name__ == "__main__":
    asyncio.run(main())
