"""京东方晨间登录：补模板 srm_boe_login + 绑薄登录 Flow。

做什么：
1. 真实租户下补流程模板 srm_boe_login（京东方-SRM晨间登录）
2. 读 rpa-flows/rpa_flow_srm_boe_login/_publish_1.0.0.json，给启用京东方门户建 ENABLED Binding

默认绑全部启用京东方门户（晨间登录按 loginAccount 去重，样本门户可能不是演示户）。

用法：
    uv run python scripts/boe/bind_boe_login.py            # 预览，不写库
    uv run python scripts/boe/bind_boe_login.py --yes      # 实际写入（全部启用京东方门户）
    uv run python scripts/boe/bind_boe_login.py --yes --demo-only  # 只绑 C000142-01

前置：先跑 rpa-engine/scripts/_publish_boe_login.py 发布 Flow。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))

from app.core.deps import async_session_factory  # noqa: E402
from app.models.base import not_deleted  # noqa: E402
from app.models.portal_account import PortalAccount  # noqa: E402
from app.models.workflow_binding import WorkflowBinding  # noqa: E402
from app.models.workflow_template import WorkflowTemplate  # noqa: E402
from app.services.json_utils import dumps_json, loads_json  # noqa: E402
from app.services.rpa_engine_client import normalize_checksum  # noqa: E402

FLOWS = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")
VERSION = "1.0.0"
DEMO_SUBCODE = "C000142-01"
TEMPLATE_CODE = "srm_boe_login"
FLOW_ID = "rpa_flow_srm_boe_login"
TEMPLATE_NAME = "京东方-SRM晨间登录"
TEMPLATE_DESC = "只登录京东方 SRM，不进发票箱单"

INPUT_SCHEMA = [
    {"name": "loginAccount", "label": "SRM账号", "type": "string", "required": False},
]


def _merge_binding_config(raw: str | None, portal_url: str) -> str:
    data = loads_json(raw or "", {})
    if not isinstance(data, dict):
        data = {}
    data["portalUrl"] = portal_url
    return dumps_json(data)


def _load_publish() -> dict:
    path = FLOWS / FLOW_ID / f"_publish_{VERSION}.json"
    if not path.exists():
        raise SystemExit(f"未发布：{path}（先跑 _publish_boe_login.py）")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "PUBLISHED":
        raise SystemExit(f"{FLOW_ID} 状态不是 PUBLISHED：{data.get('status')}")
    return data


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="实际写入（默认预览）")
    parser.add_argument("--demo-only", action="store_true", help="只绑演示门户 C000142-01")
    args = parser.parse_args()

    pub = _load_publish()

    async with async_session_factory() as db:
        portals = list(
            (
                await db.execute(
                    select(PortalAccount).where(
                        PortalAccount.category == "BOE",
                        PortalAccount.status == "ENABLED",
                        not_deleted(PortalAccount),
                    )
                )
            ).scalars().all()
        )
        if args.demo_only:
            portals = [p for p in portals if p.erp_entity_code == DEMO_SUBCODE]
        if not portals:
            raise SystemExit("没有可绑的京东方门户")
        tenant_id = portals[0].tenant_id

        template = (
            await db.execute(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.tenant_id == tenant_id,
                    WorkflowTemplate.code == TEMPLATE_CODE,
                    not_deleted(WorkflowTemplate),
                )
            )
        ).scalar_one_or_none()
        if template is None:
            print(f"[模板] 新建 {TEMPLATE_CODE}（{TEMPLATE_NAME}）")
            if args.yes:
                template = WorkflowTemplate(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    name=TEMPLATE_NAME,
                    code=TEMPLATE_CODE,
                    description=TEMPLATE_DESC,
                    entity_type="CUSTOMER",
                    category="boe-login",
                    status="ENABLED",
                    version=VERSION,
                    input_schema=dumps_json(INPUT_SCHEMA),
                    business_steps=dumps_json(
                        [{"id": "login", "name": "登录门户"}]
                    ),
                    created_by="script:bind_boe_login",
                )
                db.add(template)
                await db.flush()
        else:
            print(f"[模板] 已存在 {TEMPLATE_CODE} id={template.id}")

        if template is None:
            for portal in portals:
                print(
                    f"[Binding] 将新建 {portal.portal_name}({portal.erp_entity_code}) "
                    f"{TEMPLATE_CODE} -> {pub['rpaFlowId']} {pub['rpaFlowVersion']}"
                )
            print("预览模式，未写库。加 --yes 实际写入。")
            return

        for portal in portals:
            existing = (
                await db.execute(
                    select(WorkflowBinding).where(
                        WorkflowBinding.portal_account_id == portal.id,
                        WorkflowBinding.workflow_template_id == template.id,
                        not_deleted(WorkflowBinding),
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.rpa_flow_version == pub["rpaFlowVersion"]:
                    print(
                        f"[Binding] 已存在 {portal.portal_name} {TEMPLATE_CODE} "
                        f"ver={existing.rpa_flow_version} status={existing.status}，跳过"
                    )
                    continue
                print(
                    f"[Binding] 升级 {portal.portal_name} {TEMPLATE_CODE} "
                    f"{existing.rpa_flow_version} -> {pub['rpaFlowVersion']}"
                )
                if args.yes:
                    existing.rpa_flow_version = pub["rpaFlowVersion"]
                    existing.rpa_flow_version_id = pub["rpaFlowVersionId"]
                    existing.flow_checksum_snapshot = (
                        normalize_checksum(pub["packageChecksum"]) or ""
                    )
                    existing.workflow_template_version = VERSION
                    existing.status = "ENABLED"
                    existing.config = _merge_binding_config(
                        existing.config, portal.portal_url
                    )
                continue
            print(
                f"[Binding] 新建 {portal.portal_name}({portal.erp_entity_code}) "
                f"{TEMPLATE_CODE} -> {pub['rpaFlowId']} {pub['rpaFlowVersion']}"
            )
            if args.yes:
                db.add(
                    WorkflowBinding(
                        id=str(uuid.uuid4()),
                        portal_account_id=portal.id,
                        workflow_template_id=template.id,
                        workflow_template_version=VERSION,
                        rpa_flow_id=pub["rpaFlowId"],
                        rpa_flow_version=pub["rpaFlowVersion"],
                        rpa_flow_version_id=pub["rpaFlowVersionId"],
                        flow_checksum_snapshot=normalize_checksum(
                            pub["packageChecksum"]
                        )
                        or "",
                        config=_merge_binding_config(None, portal.portal_url),
                        status="ENABLED",
                        created_by="script:bind_boe_login",
                    )
                )
        if args.yes:
            await db.commit()
            print("已提交。")
        else:
            print("预览模式，未写库。加 --yes 实际写入。")


if __name__ == "__main__":
    asyncio.run(main())
