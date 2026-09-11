"""Bind rehearsal portal 天地伟业-芯云-正式演练 to generate 1.1.2 with dryRun=true.

Reads DATABASE_URL from service/.env only. Ignores process env.
Refuses rpa_autotask and any portal whose name does not contain 演练.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json, loads_json
from app.services.rpa_engine_client import normalize_checksum

TEST_ENV = Path(r"d:\work_space260811\autotask-workspace\service\.env")
PUBLISH_JSON = Path(
    r"d:\work_space260811\autotask-workspace\rpa-flows"
    r"\rpa_flow_srm_stmt_generate\_publish_1.1.2.json"
)
OFFICIAL_URL = "https://supplier.tiandy.com"
DEMO_HOST = "192.168.102.247"
PRODUCTION_PORTAL_NAME = "天地伟业-芯云"
TEMPLATE_CODE = "srm_stmt_generate"
FLOW_ID = "rpa_flow_srm_stmt_generate"
EXPECTED_VERSION = "1.1.2"


def load_database_url() -> str:
    for line in TEST_ENV.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key == "DATABASE_URL":
            return value.strip().strip('"').strip("'")
    raise SystemExit("DATABASE_URL missing in .env")


def db_host_name(url: str) -> str:
    return url.split("@")[-1].split("?")[0]


def is_demo_portal(portal) -> bool:
    name = getattr(portal, "portal_name", "") or ""
    url = getattr(portal, "portal_url", "") or ""
    return "test" in name.casefold() or DEMO_HOST in url


def is_rehearsal_official(portal) -> bool:
    name = (portal.portal_name or "").strip()
    url = portal.portal_url or ""
    if OFFICIAL_URL not in url:
        return False
    return "演练" in name


async def main() -> None:
    db_url = load_database_url()
    db = db_host_name(db_url)
    print("using_db", db)
    if "rpa_autotask" in db:
        raise SystemExit("refusing to bind against rpa_autotask; use 测库 .env")
    if "nodeskclaw_task" not in db:
        raise SystemExit("refusing: .env is not 测库")

    published = json.loads(PUBLISH_JSON.read_text(encoding="utf-8"))
    version = published["rpaFlowVersion"]
    version_id = published["rpaFlowVersionId"]
    checksum = normalize_checksum(published["packageChecksum"]) or ""
    flow_id = published["rpaFlowId"]
    if version != EXPECTED_VERSION or flow_id != FLOW_ID:
        raise SystemExit(f"publish json mismatch: {published}")

    engine = create_async_engine(db_url, echo=False, connect_args={"ssl": False})
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            template_rows = (
                await session.execute(
                    select(WorkflowTemplate).where(
                        WorkflowTemplate.code == TEMPLATE_CODE,
                        not_deleted(WorkflowTemplate),
                    )
                )
            ).scalars().all()
            if not template_rows:
                raise SystemExit(f"workflow template missing: {TEMPLATE_CODE}")

            updated = 0
            for template in template_rows:
                bindings = (
                    await session.execute(
                        select(WorkflowBinding, PortalAccount)
                        .join(
                            PortalAccount,
                            PortalAccount.id == WorkflowBinding.portal_account_id,
                        )
                        .where(
                            WorkflowBinding.workflow_template_id == template.id,
                            not_deleted(WorkflowBinding),
                            not_deleted(PortalAccount),
                        )
                    )
                ).all()
                for binding, portal in bindings:
                    if is_demo_portal(portal):
                        continue
                    if not is_rehearsal_official(portal):
                        print("skip", portal.portal_name, binding.rpa_flow_version)
                        continue
                    config = loads_json(binding.config, {})
                    if not isinstance(config, dict):
                        config = {}
                    config["portalUrl"] = OFFICIAL_URL
                    config["dryRun"] = True
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
                    binding.rpa_flow_id = flow_id
                    binding.rpa_flow_version = version
                    binding.rpa_flow_version_id = version_id
                    binding.flow_checksum_snapshot = checksum
                    binding.status = "ENABLED"
                    binding.config = dumps_json(config)
                    updated += 1
                    print(
                        "binding_update",
                        binding.id,
                        portal.portal_name,
                        version,
                        "dryRun=true",
                    )
                    if (portal.portal_name or "").strip() == PRODUCTION_PORTAL_NAME:
                        print("warning: bound production portal name with dryRun=true")

            if updated == 0:
                raise SystemExit("no rehearsal official generate binding found")
            await session.commit()

            rows = (
                await session.execute(
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
            for portal_name, url, bound_version, raw_config in rows:
                cfg = loads_json(raw_config, {}) if raw_config else {}
                print(
                    "generate_binding",
                    portal_name,
                    url,
                    bound_version,
                    "dryRun=",
                    cfg.get("dryRun", "<未设>"),
                )
                listed = SimpleNamespace(portal_name=portal_name, portal_url=url)
                if is_demo_portal(listed) and not str(bound_version).startswith("1.0"):
                    raise SystemExit(f"demo generate binding was changed to {bound_version}")
            print("demo generate bindings unchanged")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
