"""Create ENABLED WorkflowBindings for official-portal readonly Flows 1.1.1.

Binds only 天地伟业-国际-正式演练. Does not change demo-portal 1.0.x bindings.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.deps import async_session_factory
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json
from app.services.rpa_engine_client import normalize_checksum

OFFICIAL_PORTAL_NAME = "天地伟业-国际-正式演练"
OFFICIAL_PORTAL_URL = "https://supplier.tiandy.com"
DEMO_HOST = "192.168.102.247"
PUBLISH_JSON = Path(r"d:\work_space260811\autotask-workspace\rpa-flows\_publish_1.1.1.json")
FLOWS_ROOT = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")
WORKFLOWS = [
    ("srm_scan_pending_orders", "rpa_flow_srm_scan_pending_orders"),
    ("srm_check_reply_status", "rpa_flow_srm_check_reply_status"),
    ("srm_stmt_query_receipts", "rpa_flow_srm_stmt_query_receipts"),
]
CONFIG = dumps_json(
    {
        "portalUrl": OFFICIAL_PORTAL_URL,
        "browserSession": {
            "mode": "MANAGED",
            "headless": True,
            "channel": "chromium",
            "profileRef": None,
            "cdpEndpointRef": None,
            "closePolicy": "CLOSE_ON_FINISH",
        },
    }
)


def load_published() -> dict[str, dict]:
    if PUBLISH_JSON.exists():
        items = json.loads(PUBLISH_JSON.read_text(encoding="utf-8"))
        return {item["rpaFlowId"]: item for item in items}
    published = {}
    for _, flow_id in WORKFLOWS:
        path = FLOWS_ROOT / flow_id / "_publish_1.1.1.json"
        published[flow_id] = json.loads(path.read_text(encoding="utf-8"))
    return published


def is_demo_portal(portal: PortalAccount) -> bool:
    name = portal.portal_name or ""
    url = portal.portal_url or ""
    return "test" in name.casefold() or DEMO_HOST in url


async def main() -> None:
    published = load_published()
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
            raise SystemExit(
                f"official portal URL mismatch: {official.portal_url!r}"
            )
        print(f"official portal {official.id} {official.portal_name} {official.portal_url}")

        for code, flow_id in WORKFLOWS:
            flow = published[flow_id]
            version = flow["rpaFlowVersion"]
            version_id = flow["rpaFlowVersionId"]
            checksum = normalize_checksum(flow["packageChecksum"]) or ""
            if version != "1.1.1":
                raise SystemExit(f"{flow_id} published version is {version}, expected 1.1.1")

            template = (
                await db.execute(
                    select(WorkflowTemplate).where(
                        WorkflowTemplate.tenant_id == official.tenant_id,
                        WorkflowTemplate.code == code,
                        not_deleted(WorkflowTemplate),
                    )
                )
            ).scalar_one_or_none()
            if template is None:
                raise SystemExit(f"workflow template missing: {code}")

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
                    config=CONFIG,
                    created_by=official.created_by,
                )
                db.add(binding)
                print("binding_insert", code, binding.id, version)
            else:
                binding.rpa_flow_id = flow_id
                binding.rpa_flow_version = version
                binding.rpa_flow_version_id = version_id
                binding.flow_checksum_snapshot = checksum
                binding.status = "ENABLED"
                binding.config = CONFIG
                print("binding_update", code, binding.id, version)

        await db.commit()

        demo_rows = (
            await db.execute(
                select(
                    PortalAccount.portal_name,
                    PortalAccount.portal_url,
                    WorkflowTemplate.code,
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
                    WorkflowTemplate.code.in_([code for code, _ in WORKFLOWS]),
                )
            )
        ).all()
        demo_ok = True
        for name, url, code, version in demo_rows:
            portal = SimplePortal(name, url)
            if not is_demo_portal(portal):
                continue
            print("demo_keep", name, code, version)
            if not str(version).startswith("1.0"):
                demo_ok = False
                print("ERROR demo binding was changed to", version)
        if not demo_ok:
            raise SystemExit("demo portal bindings must stay on 1.0.x")
        print("demo bindings unchanged (1.0.x)")


class SimplePortal:
    def __init__(self, portal_name: str, portal_url: str):
        self.portal_name = portal_name
        self.portal_url = portal_url


if __name__ == "__main__":
    asyncio.run(main())
