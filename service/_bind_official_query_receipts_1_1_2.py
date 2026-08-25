"""Switch official-portal receipt query Binding to 1.1.2. Does not change demo 1.0.x."""
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

OFFICIAL_PORTAL_NAME = "天地伟业-国际-正式演练"
PUBLISH = Path(
    r"d:\work_space260811\autotask-workspace\rpa-flows\rpa_flow_srm_stmt_query_receipts\_publish_1.1.2.json"
)
TEMPLATE_CODE = "srm_stmt_query_receipts"
DEMO_HOST = "192.168.102.247"


async def main() -> None:
    published = json.loads(PUBLISH.read_text(encoding="utf-8"))
    version = published["rpaFlowVersion"]
    if version != "1.1.2":
        raise SystemExit(f"expected 1.1.2, got {version}")
    checksum = normalize_checksum(published["packageChecksum"]) or ""
    async with async_session_factory() as db:
        official = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == OFFICIAL_PORTAL_NAME,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
        if official is None:
            raise SystemExit(f"portal not found: {OFFICIAL_PORTAL_NAME}")
        template = (
            await db.execute(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.tenant_id == official.tenant_id,
                    WorkflowTemplate.code == TEMPLATE_CODE,
                    not_deleted(WorkflowTemplate),
                )
            )
        ).scalar_one_or_none()
        if template is None:
            raise SystemExit(f"template missing: {TEMPLATE_CODE}")
        binding = (
            await db.execute(
                select(WorkflowBinding).where(
                    WorkflowBinding.portal_account_id == official.id,
                    WorkflowBinding.workflow_template_id == template.id,
                    not_deleted(WorkflowBinding),
                )
            )
        ).scalar_one_or_none()
        if binding is None:
            raise SystemExit("official query-receipts binding missing")
        binding.rpa_flow_id = published["rpaFlowId"]
        binding.rpa_flow_version = version
        binding.rpa_flow_version_id = published["rpaFlowVersionId"]
        binding.flow_checksum_snapshot = checksum
        binding.status = "ENABLED"
        print("binding_update", binding.id, version, published["rpaFlowVersionId"])
        await db.commit()

        rows = (
            await db.execute(
                select(
                    PortalAccount.portal_name,
                    PortalAccount.portal_url,
                    WorkflowBinding.rpa_flow_version,
                )
                .join(
                    WorkflowBinding,
                    WorkflowBinding.portal_account_id == PortalAccount.id,
                )
                .join(
                    WorkflowTemplate,
                    WorkflowTemplate.id == WorkflowBinding.workflow_template_id,
                )
                .where(
                    not_deleted(PortalAccount),
                    not_deleted(WorkflowBinding),
                    not_deleted(WorkflowTemplate),
                    WorkflowTemplate.code == TEMPLATE_CODE,
                )
            )
        ).all()
        for name, url, bound_version in rows:
            print("query_receipts_binding", name, url, bound_version)
            if DEMO_HOST in (url or "") and not str(bound_version).startswith("1.0"):
                raise SystemExit(
                    f"demo query-receipts binding was changed to {bound_version}"
                )
        print("demo query-receipts bindings unchanged")


if __name__ == "__main__":
    asyncio.run(main())
