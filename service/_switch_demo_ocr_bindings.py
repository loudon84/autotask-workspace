"""Switch demo-portal login Flows to OCR packages. Does not touch the official portal."""
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

PUBLISH = Path(r"d:\work_space260811\autotask-workspace\rpa-flows\_publish_demo_ocr.json")
DEMO_HOST = "192.168.102.247"
OFFICIAL_URL = "supplier.tiandy.com"


async def main() -> None:
    published = {item["workflowCode"]: item for item in json.loads(PUBLISH.read_text(encoding="utf-8"))}
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
                    WorkflowTemplate.code.in_(list(published.keys())),
                    not_deleted(WorkflowBinding),
                    not_deleted(PortalAccount),
                    not_deleted(WorkflowTemplate),
                )
            )
        ).all()
        for binding, portal, template in rows:
            url = portal.portal_url or ""
            item = published[template.code]
            if OFFICIAL_URL in url:
                print("skip_official", portal.portal_name, template.code, binding.rpa_flow_version)
                continue
            if DEMO_HOST not in url:
                print("skip_other", portal.portal_name, template.code, url)
                continue
            print(
                "switch",
                portal.portal_name,
                template.code,
                binding.rpa_flow_version,
                "->",
                item["rpaFlowVersion"],
            )
            binding.rpa_flow_version = item["rpaFlowVersion"]
            binding.rpa_flow_version_id = item["rpaFlowVersionId"]
            binding.flow_checksum_snapshot = normalize_checksum(item["packageChecksum"]) or ""
            binding.status = "ENABLED"
        await db.commit()
        print("committed")


if __name__ == "__main__":
    asyncio.run(main())
