"""Bind official-portal check-reply 1.1.2 to 天地伟业-国际-正式演练.

Does not change demo-portal check-reply bindings.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json, loads_json
from app.services.rpa_engine_client import normalize_checksum

OFFICIAL_PORTAL_NAME = "天地伟业-国际-正式演练"
OFFICIAL_PORTAL_URL = "https://supplier.tiandy.com"
DEMO_HOST = "192.168.102.247"
TEMPLATE_CODE = "srm_check_reply_status"
FLOW_ID = "rpa_flow_srm_check_reply_status"
EXPECTED_VERSION = "1.1.4"
PUBLISH_JSON = Path(
    r"d:\work_space260811\autotask-workspace\rpa-flows"
    r"\rpa_flow_srm_check_reply_status\_publish_1.1.4.json"
)
SCAN_TEMPLATE_CODE = "srm_scan_pending_orders"


def is_demo_portal(portal: PortalAccount) -> bool:
    name = portal.portal_name or ""
    url = portal.portal_url or ""
    return "test" in name.casefold() or DEMO_HOST in url


async def main() -> None:
    published = json.loads(PUBLISH_JSON.read_text(encoding="utf-8"))
    version = published["rpaFlowVersion"]
    version_id = published["rpaFlowVersionId"]
    checksum = normalize_checksum(published["packageChecksum"]) or ""
    flow_id = published["rpaFlowId"]
    if version != EXPECTED_VERSION or flow_id != FLOW_ID:
        raise SystemExit(f"publish json mismatch: {published}")

    async with async_session_factory() as db:
        official = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == OFFICIAL_PORTAL_NAME,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one()
        if OFFICIAL_PORTAL_URL not in (official.portal_url or ""):
            raise SystemExit(f"official portal URL mismatch: {official.portal_url!r}")

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
            raise SystemExit(f"workflow template missing: {TEMPLATE_CODE}")

        scan_template = (
            await db.execute(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.tenant_id == official.tenant_id,
                    WorkflowTemplate.code == SCAN_TEMPLATE_CODE,
                    not_deleted(WorkflowTemplate),
                )
            )
        ).scalar_one_or_none()
        scan_binding = None
        if scan_template is not None:
            scan_binding = (
                await db.execute(
                    select(WorkflowBinding).where(
                        WorkflowBinding.portal_account_id == official.id,
                        WorkflowBinding.workflow_template_id == scan_template.id,
                        not_deleted(WorkflowBinding),
                    )
                )
            ).scalar_one_or_none()
        config = loads_json(scan_binding.config, {}) if scan_binding else {}
        if not isinstance(config, dict):
            config = {}
        config["portalUrl"] = OFFICIAL_PORTAL_URL
        config.pop("dryRun", None)
        config.setdefault(
            "browserSession",
            {
                "mode": "MANAGED",
                "headless": True,
                "channel": "chromium",
                "profileRef": None,
                "cdpEndpointRef": None,
                "closePolicy": "CLOSE_ON_FINISH",
            },
        )

        binding = (
            await db.execute(
                select(WorkflowBinding).where(
                    WorkflowBinding.portal_account_id == official.id,
                    WorkflowBinding.workflow_template_id == template.id,
                    not_deleted(WorkflowBinding),
                )
            )
        ).scalar_one()
        binding.rpa_flow_id = flow_id
        binding.rpa_flow_version = version
        binding.rpa_flow_version_id = version_id
        binding.flow_checksum_snapshot = checksum
        binding.status = "ENABLED"
        binding.config = dumps_json(config)
        print("binding_update", binding.id, version)
        await db.commit()

        demo_rows = (
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
        for name, url, bound_version in demo_rows:
            portal = SimpleNamespace(portal_name=name, portal_url=url)
            if not is_demo_portal(portal):
                print("official_bound", name, bound_version)
                continue
            print("demo_keep", name, bound_version)
            if str(bound_version) == EXPECTED_VERSION:
                raise SystemExit(f"demo portal binding was changed to {bound_version}")
        print("demo check-reply bindings unchanged")

    await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
