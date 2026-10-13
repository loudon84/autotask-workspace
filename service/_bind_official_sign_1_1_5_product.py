"""Bind production portal 天地伟业-芯云 to sign 1.1.5 without dryRun.

Reads DATABASE_URL from service/.env.product only. Ignores process env.
Refuses any DB other than rpa_autotask, any portal whose name contains 演练,
and local-engine publish receipts.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json, loads_json
from app.services.rpa_engine_client import normalize_checksum

PRODUCT_ENV = Path(r"d:\work_space260811\autotask-workspace\service\.env.product")
PUBLISH_JSON = Path(
    r"d:\work_space260811\autotask-workspace\rpa-flows"
    r"\rpa_flow_srm_sign_order\_publish_1.1.5.product.json"
)
OFFICIAL_URL = "https://supplier.tiandy.com"
PRODUCTION_PORTAL_NAME = "天地伟业-芯云"
TEMPLATE_CODE = "srm_sign_order"
TEMPLATE_ID = "4540f066-5e1b-4ef6-90f4-31f0efe54bc0"
FLOW_ID = "rpa_flow_srm_sign_order"
EXPECTED_VERSION = "1.1.5"
# Local 4610 rehearsal receipt — never bind this into production DB.
LOCAL_VERSION_IDS = {
    "5314dfe8-34e7-4918-a461-69bc236305ae",
}
BROWSER = {
    "mode": "MANAGED",
    "headless": True,
    "channel": "chromium",
    "profileRef": None,
    "cdpEndpointRef": None,
    "closePolicy": "CLOSE_ON_FINISH",
}
SIGN_TEMPLATE_SEED = {
    "id": TEMPLATE_ID,
    "name": "天地伟业·订单回签",
    "code": TEMPLATE_CODE,
    "description": "v2.0 流程实例：复核全行交期后签章",
    "entity_type": "CUSTOMER",
    "category": "procurement",
    "status": "ENABLED",
    "version": "1.0.0",
    "input_schema": [{"name": "po_no", "type": "string", "required": True}],
    "business_steps": [
        {"id": "srm.login", "name": "登录门户", "type": "srm.login"},
        {"id": "srm.search_po", "name": "搜索并打开采购订单", "type": "srm.search_po"},
        {"id": "srm.sign_order", "name": "发起签章", "type": "srm.sign_order"},
    ],
}


def load_product_database_url() -> str:
    for line in PRODUCT_ENV.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key == "DATABASE_URL":
            return value.strip().strip('"').strip("'")
    raise SystemExit("DATABASE_URL missing in .env.product")


def db_host_name(url: str) -> str:
    return url.split("@")[-1].split("?")[0]


async def main() -> None:
    db_url = load_product_database_url()
    db = db_host_name(db_url)
    print("using_db", db)
    if "rpa_autotask" not in db:
        raise SystemExit("refusing: .env.product is not rpa_autotask")
    if "nodeskclaw_task" in db:
        raise SystemExit("refusing: this script is production-only")

    published = json.loads(PUBLISH_JSON.read_text(encoding="utf-8"))
    version = published["rpaFlowVersion"]
    version_id = published["rpaFlowVersionId"]
    checksum = normalize_checksum(published["packageChecksum"]) or ""
    flow_id = published["rpaFlowId"]
    if version != EXPECTED_VERSION or flow_id != FLOW_ID:
        raise SystemExit(f"publish json mismatch: {published}")
    if version_id in LOCAL_VERSION_IDS:
        raise SystemExit("refusing local-engine versionId; use product publish receipt")
    if published.get("engine") != "http://192.168.102.247:4610":
        raise SystemExit(f"refusing non-product engine receipt: {published.get('engine')}")

    engine = create_async_engine(db_url, echo=False, connect_args={"ssl": False})
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            template = (
                await session.execute(
                    select(WorkflowTemplate).where(
                        WorkflowTemplate.code == TEMPLATE_CODE,
                        not_deleted(WorkflowTemplate),
                    )
                )
            ).scalar_one_or_none()
            if template is None:
                # 正式库此前未种签章模板；用同租户已有模板的 tenant/created_by 补一行再绑。
                sample = (
                    await session.execute(
                        select(WorkflowTemplate).where(
                            not_deleted(WorkflowTemplate),
                        ).limit(1)
                    )
                ).scalar_one_or_none()
                if sample is None:
                    raise SystemExit("no workflow templates on production DB to copy tenant from")
                template = WorkflowTemplate(
                    id=SIGN_TEMPLATE_SEED["id"],
                    tenant_id=sample.tenant_id,
                    name=SIGN_TEMPLATE_SEED["name"],
                    code=SIGN_TEMPLATE_SEED["code"],
                    description=SIGN_TEMPLATE_SEED["description"],
                    entity_type=SIGN_TEMPLATE_SEED["entity_type"],
                    category=SIGN_TEMPLATE_SEED["category"],
                    status=SIGN_TEMPLATE_SEED["status"],
                    version=SIGN_TEMPLATE_SEED["version"],
                    input_schema=dumps_json(SIGN_TEMPLATE_SEED["input_schema"]),
                    business_steps=dumps_json(SIGN_TEMPLATE_SEED["business_steps"]),
                    created_by=sample.created_by,
                )
                session.add(template)
                await session.flush()
                print("template_insert", template.id, TEMPLATE_CODE)

            portals = (
                await session.execute(
                    select(PortalAccount).where(not_deleted(PortalAccount))
                )
            ).scalars().all()
            updated = 0
            for portal in portals:
                name = (portal.portal_name or "").strip()
                if "演练" in name:
                    print("skip rehearsal", name)
                    continue
                if name != PRODUCTION_PORTAL_NAME:
                    continue
                url = portal.portal_url or ""
                if OFFICIAL_URL not in url:
                    raise SystemExit(f"production portal URL unexpected: {url}")

                binding = (
                    await session.execute(
                        select(WorkflowBinding).where(
                            WorkflowBinding.portal_account_id == portal.id,
                            WorkflowBinding.workflow_template_id == template.id,
                            not_deleted(WorkflowBinding),
                        )
                    )
                ).scalar_one_or_none()
                config = {
                    "portalUrl": OFFICIAL_URL,
                    "browserSession": BROWSER,
                }
                # Real sign: never leave dryRun on production.
                if binding is None:
                    binding = WorkflowBinding(
                        id=str(uuid.uuid4()),
                        portal_account_id=portal.id,
                        workflow_template_id=template.id,
                        workflow_template_version=template.version or "1.0.0",
                        rpa_engine_type="PLAYWRIGHT_CDP",
                        rpa_flow_id=flow_id,
                        rpa_flow_version=version,
                        rpa_flow_version_id=version_id,
                        flow_checksum_snapshot=checksum,
                        status="ENABLED",
                        config=dumps_json(config),
                        created_by=portal.created_by,
                    )
                    session.add(binding)
                    print("binding_insert", binding.id, name, version, "no dryRun")
                else:
                    existing = loads_json(binding.config, {})
                    if not isinstance(existing, dict):
                        existing = {}
                    existing.pop("dryRun", None)
                    existing["portalUrl"] = OFFICIAL_URL
                    existing["browserSession"] = BROWSER
                    binding.rpa_flow_id = flow_id
                    binding.rpa_flow_version = version
                    binding.rpa_flow_version_id = version_id
                    binding.flow_checksum_snapshot = checksum
                    binding.status = "ENABLED"
                    binding.config = dumps_json(existing)
                    print(
                        "binding_update",
                        binding.id,
                        name,
                        version,
                        version_id,
                        "dryRun=removed",
                    )
                updated += 1

            if updated != 1:
                raise SystemExit(
                    f"expected exactly 1 production sign binding, got {updated}"
                )
            await session.commit()

            rows = (
                await session.execute(
                    select(
                        PortalAccount.portal_name,
                        PortalAccount.portal_url,
                        WorkflowBinding.rpa_flow_version,
                        WorkflowBinding.rpa_flow_version_id,
                        WorkflowBinding.status,
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
            for portal_name, url, bound_version, bound_id, status, raw_config in rows:
                cfg = loads_json(raw_config, {}) if raw_config else {}
                print(
                    "sign_binding",
                    portal_name,
                    url,
                    bound_version,
                    bound_id,
                    status,
                    "dryRun=",
                    cfg.get("dryRun", "<未设>"),
                )
                if portal_name == PRODUCTION_PORTAL_NAME and cfg.get("dryRun") is True:
                    raise SystemExit("production sign binding still has dryRun=true")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
