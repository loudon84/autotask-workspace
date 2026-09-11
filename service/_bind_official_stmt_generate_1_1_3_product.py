"""Bind production portal 天地伟业-芯云 to generate 1.1.3 without dryRun.

Reads DATABASE_URL from service/.env.product only. Ignores process env.
Refuses any DB other than rpa_autotask and any portal whose name contains 演练.
"""
from __future__ import annotations

import asyncio
import json
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
    r"\rpa_flow_srm_stmt_generate\_publish_1.1.3.product.json"
)
PRODUCTION_PORTAL_NAME = "天地伟业-芯云"
TEMPLATE_CODE = "srm_stmt_generate"
FLOW_ID = "rpa_flow_srm_stmt_generate"
EXPECTED_VERSION = "1.1.3"
LOCAL_VERSION_IDS = {
    "55637e52-a893-4f29-a5c8-89235effbd10",
    "b16ead16-a4ab-4b68-a002-ed3bcd5f3b9b",
    "f562f15b-8855-4330-a36c-6fa8af0f7d5b",
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
        raise SystemExit("refusing non-product engine receipt")

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
                    name = (portal.portal_name or "").strip()
                    if "演练" in name:
                        print("skip rehearsal", name, binding.rpa_flow_version)
                        continue
                    if name != PRODUCTION_PORTAL_NAME:
                        print("skip", name, binding.rpa_flow_version)
                        continue
                    config = loads_json(binding.config, {})
                    if not isinstance(config, dict):
                        config = {}
                    config.pop("dryRun", None)
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
                        name,
                        version,
                        version_id,
                        "dryRun=removed",
                    )

            if updated != 1:
                raise SystemExit(f"expected exactly 1 production generate binding, got {updated}")
            await session.commit()

            rows = (
                await session.execute(
                    select(
                        PortalAccount.portal_name,
                        PortalAccount.portal_url,
                        WorkflowBinding.rpa_flow_version,
                        WorkflowBinding.rpa_flow_version_id,
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
            for portal_name, url, bound_version, bound_id, raw_config in rows:
                cfg = loads_json(raw_config, {}) if raw_config else {}
                print(
                    "generate_binding",
                    portal_name,
                    url,
                    bound_version,
                    bound_id,
                    "dryRun=",
                    cfg.get("dryRun", "<未设>"),
                )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
