"""京东方发票箱单：补模板 + 绑 Binding（演示门户）。

做什么：
1. 真实租户下补 4 个流程模板（seed JSON 里只有 seed-tenant-001 的，真实租户没有）
2. 读 rpa-flows/<flow>/_publish_<ver>.json，给演示门户（C000142-01）建 ENABLED Binding
   enrich/save_draft/submit 用 1.0.23；delete_draft 用 1.0.1

用法：
    uv run python scripts/boe/bind_boe_pack_flows.py            # 预览，不写库
    uv run python scripts/boe/bind_boe_pack_flows.py --yes      # 实际写入
    uv run python scripts/boe/bind_boe_pack_flows.py --yes --all-portals  # 绑所有京东方门户

前置：先跑 rpa-engine/scripts/_publish_boe_pack_flows.py 发布 Flow。
     只发删除草稿：uv run python scripts/_publish_boe_pack_flows.py --only-delete
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
VERSION = "1.0.23"
DELETE_VERSION = "1.0.1"
DEMO_SUBCODE = "C000142-01"

# (template_code, flow_id, 模板名, 描述, 步骤id/名)
TEMPLATES = [
    (
        "srm_boe_pack_enrich",
        "rpa_flow_srm_boe_pack_enrich",
        "京东方-RPA补全项目信息行",
        "按 PO+料号查询采购凭证并回写行字段",
        ("srm.enrich_lines", "补全项目信息行"),
    ),
    (
        "srm_boe_pack_save_draft",
        "rpa_flow_srm_boe_pack_save_draft",
        "京东方-保存SRM草稿单",
        "按 Client 单据重建发票箱单并保存 SRM 草稿",
        ("srm.save_draft", "保存草稿"),
    ),
    (
        "srm_boe_pack_submit",
        "rpa_flow_srm_boe_pack_submit",
        "京东方-提交SRM单据",
        "打开已有 SRM 草稿做变更单提交",
        ("srm.submit", "提交单据"),
    ),
    (
        "srm_boe_pack_delete_draft",
        "rpa_flow_srm_boe_pack_delete_draft",
        "京东方-删除SRM草稿",
        "作废前按流水号删除 SRM 草稿；没有则视为已删",
        ("srm.delete_draft", "删除草稿"),
    ),
]

INPUT_SCHEMA = [
    {"name": "instanceId", "label": "流程实例", "type": "string", "required": True},
    {"name": "docNo", "label": "交货计划单号", "type": "string", "required": True},
    {"name": "srmDraftNo", "label": "发票箱单流水号", "type": "string", "required": False},
]


def _template_version(code: str) -> str:
    return DELETE_VERSION if code == "srm_boe_pack_delete_draft" else VERSION


def _merge_binding_config(raw: str | None, portal_url: str, template_code: str) -> str:
    data = loads_json(raw or "", {})
    if not isinstance(data, dict):
        data = {}
    data["portalUrl"] = portal_url
    if template_code == "srm_boe_pack_submit":
        data["dryRun"] = True
    return dumps_json(data)


def _load_publish(flow_id: str, version: str = VERSION) -> dict:
    path = FLOWS / flow_id / f"_publish_{version}.json"
    if not path.exists():
        raise SystemExit(f"未发布：{path}（先跑 _publish_boe_pack_flows.py）")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "PUBLISHED":
        raise SystemExit(f"{flow_id} 状态不是 PUBLISHED：{data.get('status')}")
    return data


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="实际写入（默认预览）")
    parser.add_argument("--all-portals", action="store_true", help="绑所有启用京东方门户")
    args = parser.parse_args()

    publishes = {}
    for code, flow, *_ in TEMPLATES:
        publishes[code] = _load_publish(flow, _template_version(code))

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
        if not args.all_portals:
            portals = [p for p in portals if p.erp_entity_code == DEMO_SUBCODE]
        if not portals:
            raise SystemExit("没有可绑的京东方门户")
        tenant_id = portals[0].tenant_id

        for code, _flow, name, desc, step in TEMPLATES:
            tmpl_ver = _template_version(code)
            template = (
                await db.execute(
                    select(WorkflowTemplate).where(
                        WorkflowTemplate.tenant_id == tenant_id,
                        WorkflowTemplate.code == code,
                        not_deleted(WorkflowTemplate),
                    )
                )
            ).scalar_one_or_none()
            if template is None:
                print(f"[模板] 新建 {code}（{name}）")
                if args.yes:
                    template = WorkflowTemplate(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        name=name,
                        code=code,
                        description=desc,
                        entity_type="CUSTOMER",
                        category="boe-packing",
                        status="ENABLED",
                        version=tmpl_ver,
                        input_schema=dumps_json(INPUT_SCHEMA),
                        business_steps=dumps_json(
                            [
                                {"id": "login", "name": "登录门户"},
                                {"id": step[0], "name": step[1]},
                            ]
                        ),
                        created_by="script:bind_boe_pack_flows",
                    )
                    db.add(template)
                    await db.flush()
            else:
                print(f"[模板] 已存在 {code} id={template.id}")

            pub = publishes[code]
            if template is None:
                # 预览模式：模板还没建，Binding 必然也不存在
                for portal in portals:
                    print(
                        f"[Binding] 将新建 {portal.portal_name}({portal.erp_entity_code}) "
                        f"{code} -> {pub['rpaFlowId']} {pub['rpaFlowVersion']}"
                    )
                continue
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
                            f"[Binding] 已存在 {portal.portal_name} {code} "
                            f"ver={existing.rpa_flow_version} status={existing.status}，跳过"
                        )
                        continue
                    print(
                        f"[Binding] 升级 {portal.portal_name} {code} "
                        f"{existing.rpa_flow_version} -> {pub['rpaFlowVersion']}"
                    )
                    if args.yes:
                        existing.rpa_flow_version = pub["rpaFlowVersion"]
                        existing.rpa_flow_version_id = pub["rpaFlowVersionId"]
                        existing.flow_checksum_snapshot = (
                            normalize_checksum(pub["packageChecksum"]) or ""
                        )
                        existing.workflow_template_version = tmpl_ver
                        existing.status = "ENABLED"
                        existing.config = _merge_binding_config(
                            existing.config, portal.portal_url, code
                        )
                    continue
                print(
                    f"[Binding] 新建 {portal.portal_name}({portal.erp_entity_code}) "
                    f"{code} -> {pub['rpaFlowId']} {pub['rpaFlowVersion']}"
                )
                if args.yes:
                    db.add(
                        WorkflowBinding(
                            id=str(uuid.uuid4()),
                            portal_account_id=portal.id,
                            workflow_template_id=template.id,
                            workflow_template_version=tmpl_ver,
                            rpa_flow_id=pub["rpaFlowId"],
                            rpa_flow_version=pub["rpaFlowVersion"],
                            rpa_flow_version_id=pub["rpaFlowVersionId"],
                            flow_checksum_snapshot=normalize_checksum(
                                pub["packageChecksum"]
                            )
                            or "",
                            config=_merge_binding_config(
                                None, portal.portal_url, code
                            ),
                            status="ENABLED",
                            created_by="script:bind_boe_pack_flows",
                        )
                    )
        if args.yes:
            await db.commit()
            print("已提交。")
        else:
            print("预览模式，未写库。加 --yes 实际写入。")


if __name__ == "__main__":
    asyncio.run(main())
