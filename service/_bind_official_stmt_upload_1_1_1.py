"""Bind official statement upload invoice 1.1.1. Scan is allowed; do not set dryRun. Demo stays 1.0.6."""
from __future__ import annotations

import asyncio
import json
import uuid
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
TEMPLATE_CODE = "srm_stmt_upload_invoice"
FLOW_ID = "rpa_flow_srm_stmt_upload_invoice"
EXPECTED_VERSION = "1.1.1"
PUBLISH_JSON = Path(
    r"d:\work_space260811\autotask-workspace\rpa-flows"
    r"\rpa_flow_srm_stmt_upload_invoice\_publish_1.1.1.json"
)
QUERY_TEMPLATE_CODE = "srm_stmt_query_receipts"


def is_demo_portal(portal) -> bool:
    name = getattr(portal, "portal_name", "") or ""
    url = getattr(portal, "portal_url", "") or ""
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
        ).scalar_one_or_none()
        if official is None:
            raise SystemExit(f"portal not found: {OFFICIAL_PORTAL_NAME}")
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

        query_template = (
            await db.execute(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.tenant_id == official.tenant_id,
                    WorkflowTemplate.code == QUERY_TEMPLATE_CODE,
                    not_deleted(WorkflowTemplate),
                )
            )
        ).scalar_one_or_none()
        query_binding = None
        if query_template is not None:
            query_binding = (
                await db.execute(
                    select(WorkflowBinding).where(
                        WorkflowBinding.portal_account_id == official.id,
                        WorkflowBinding.workflow_template_id == query_template.id,
                        not_deleted(WorkflowBinding),
                    )
                )
            ).scalar_one_or_none()
        config = loads_json(query_binding.config, {}) if query_binding else {}
        if not isinstance(config, dict):
            config = {}
        config["portalUrl"] = OFFICIAL_PORTAL_URL
        config.pop("dryRun", None)
        config.pop("dry_run", None)
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
        ).scalar_one_or_none()
        if binding is None:
            binding = WorkflowBinding(
                id=str(uuid.uuid4()),
                portal_account_id=official.id,
                workflow_template_id=template.id,
                workflow_template_version=template.version or "1.0.0",
                rpa_engine_type="PLAYWRIGHT_CDP",
                rpa_flow_id=flow_id,
                rpa_flow_version=version,
                rpa_flow_version_id=version_id,
                flow_checksum_snapshot=checksum,
                status="ENABLED",
                config=dumps_json(config),
                created_by=official.created_by,
            )
            db.add(binding)
            print("binding_insert", binding.id, version, "scan-only no dryRun")
        else:
            binding.rpa_flow_id = flow_id
            binding.rpa_flow_version = version
            binding.rpa_flow_version_id = version_id
            binding.flow_checksum_snapshot = checksum
            binding.status = "ENABLED"
            binding.config = dumps_json(config)
            print("binding_update", binding.id, version, "scan-only no dryRun")

        await db.commit()

        rows = (
            await db.execute(
                select(
                    PortalAccount.portal_name,
                    PortalAccount.portal_url,
                    WorkflowBinding.rpa_flow_version,
                    WorkflowBinding.config,
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
        for name, url, bound_version, raw_config in rows:
            cfg = loads_json(raw_config, {}) if raw_config else {}
            print(
                "upload_binding",
                name,
                url,
                bound_version,
                "dryRun=",
                cfg.get("dryRun", "<未设>"),
            )
            portal = SimpleNamespace(portal_name=name, portal_url=url)
            if is_demo_portal(portal) and not str(bound_version).startswith("1.0"):
                raise SystemExit(f"demo upload binding was changed to {bound_version}")
        print("demo upload bindings unchanged")

    await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
