# -*- coding: utf-8 -*-
"""Empty env 阶段 A：按正式演练建模板并绑 Binding。

不绑填交期/签章。调度写入 enabled=false，不插入 scheduler_jobs。
生成/提交 dryRun=true。扫单带样例 treatAsPending。
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.models.workflow_template_version import WorkflowTemplateVersion
from app.services.json_utils import dumps_json, loads_json
from app.services.rpa_engine_client import normalize_checksum

FLOWS = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")
PORTAL_NAME = "天地伟业-芯云-正式演练"
PORTAL_URL = "https://supplier.tiandy.com"
DEMO_HOST = "192.168.102.247"

BROWSER = {
    "mode": "MANAGED",
    "headless": True,
    "channel": "chromium",
    "profileRef": None,
    "cdpEndpointRef": None,
    "closePolicy": "CLOSE_ON_FINISH",
}

PO_INPUT = [{"name": "po_no", "label": "采购订单号", "type": "string", "required": True}]

TEMPLATES = [
    {
        "code": "srm_scan_pending_orders",
        "name": "天地伟业-扫待签章订单",
        "category": "procurement",
        "input_schema": [],
        "business_steps": [{"id": "srm.scan", "name": "扫待签章"}],
    },
    {
        "code": "srm_prepare_erp_order",
        "name": "天地伟业-建 SDMS 销售订单",
        "category": "procurement",
        "input_schema": PO_INPUT,
        "business_steps": [{"id": "srm.prepare", "name": "建销售订单"}],
    },
    {
        "code": "srm_check_reply_status",
        "name": "天地伟业-回签轮询",
        "category": "procurement",
        "input_schema": PO_INPUT,
        "business_steps": [{"id": "srm.check_reply", "name": "回签探测"}],
    },
    {
        "code": "srm_upload_order_attachment",
        "name": "天地伟业-下载签章合同上传 SDMS",
        "category": "procurement",
        "input_schema": PO_INPUT,
        "business_steps": [{"id": "srm.upload_contract", "name": "下合同"}],
    },
    {
        "code": "srm_stmt_query_receipts",
        "name": "天地伟业-收货列表查询",
        "category": "statement",
        "input_schema": [
            {"name": "dateStart", "label": "入库确认开始日期", "type": "string", "required": True},
            {"name": "dateEnd", "label": "入库确认结束日期", "type": "string", "required": True},
        ],
        "business_steps": [{"id": "srm.query_receipts", "name": "查询收货列表"}],
    },
    {
        "code": "srm_stmt_generate",
        "name": "天地伟业-生成对账单",
        "category": "statement",
        "input_schema": [
            {"name": "dateStart", "label": "入库确认开始日期", "type": "string", "required": True},
            {"name": "dateEnd", "label": "入库确认结束日期", "type": "string", "required": True},
            {"name": "lines", "label": "勾选行", "type": "array", "required": True},
        ],
        "business_steps": [{"id": "srm.generate_statement", "name": "生成对账单"}],
    },
    {
        "code": "srm_stmt_upload_invoice",
        "name": "天地伟业-上传对账发票",
        "category": "statement",
        "input_schema": [
            {"name": "checkDate", "label": "对账日期", "type": "string", "required": True},
            {"name": "checkAmount", "label": "对账金额", "type": "number", "required": True},
            {"name": "filePaths", "label": "发票文件路径", "type": "array", "required": True},
        ],
        "business_steps": [{"id": "srm.upload_invoice", "name": "扫描上传发票"}],
    },
    {
        "code": "srm_stmt_submit_review",
        "name": "天地伟业-提交对账审核",
        "category": "statement",
        "input_schema": [
            {"name": "checkDate", "label": "对账日期", "type": "string", "required": True},
            {"name": "checkAmount", "label": "对账金额", "type": "number", "required": True},
            {"name": "filePaths", "label": "发票文件路径", "type": "array", "required": True},
        ],
        "business_steps": [
            {"id": "srm.upload_invoice", "name": "扫描上传发票"},
            {"id": "srm.submit_review", "name": "提交审核"},
        ],
    },
]

BINDINGS = [
    {
        "code": "srm_scan_pending_orders",
        "publish": FLOWS / "rpa_flow_srm_scan_pending_orders" / "_publish_1.1.3.json",
        "version": "1.1.3",
        "config": {
            "searches": [
                {"replyStatus": "待签章"},
                {"poNo": "POJS2607170008", "treatAsPending": True},
            ],
            "schedule": {
                "enabled": False,
                "cron": "0 8 * * *",
                "processName": "客户订单",
                "actionName": "扫单",
            },
        },
    },
    {
        "code": "srm_prepare_erp_order",
        "publish": FLOWS
        / "rpa_flow_supplier_portal_prepare_erp_order"
        / "_publish_1.2.20.json",
        "version": "1.2.20",
        "config": {},
    },
    {
        "code": "srm_check_reply_status",
        "publish": FLOWS / "rpa_flow_srm_check_reply_status" / "_publish_1.1.4.json",
        "version": "1.1.4",
        "config": {
            "schedule": {
                "enabled": False,
                "cron": "*/30 * * * *",
                "processName": "客户订单",
                "actionName": "回签轮询",
            },
        },
    },
    {
        "code": "srm_upload_order_attachment",
        "publish": FLOWS
        / "rpa_flow_supplier_portal_upload_order_attachment"
        / "_publish_1.3.3.json",
        "version": "1.3.3",
        "config": {},
    },
    {
        "code": "srm_stmt_query_receipts",
        "publish": FLOWS / "rpa_flow_srm_stmt_query_receipts" / "_publish_1.1.3.json",
        "version": "1.1.3",
        "config": {},
    },
    {
        "code": "srm_stmt_generate",
        "publish": FLOWS / "rpa_flow_srm_stmt_generate" / "_publish_1.1.0.json",
        "version": "1.1.0",
        "config": {"dryRun": True},
    },
    {
        "code": "srm_stmt_upload_invoice",
        "publish": FLOWS / "rpa_flow_srm_stmt_upload_invoice" / "_publish_1.1.2.json",
        "version": "1.1.2",
        "config": {},
    },
    {
        "code": "srm_stmt_submit_review",
        "publish": FLOWS / "rpa_flow_srm_stmt_submit_review" / "_publish_1.1.5.json",
        "version": "1.1.5",
        "config": {"dryRun": True},
    },
]


async def find_portal(db) -> PortalAccount:
    official = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.portal_name == PORTAL_NAME,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if official is None:
        official = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_url.contains(PORTAL_URL),
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
    if official is None:
        rows = (
            await db.execute(
                select(PortalAccount.portal_name, PortalAccount.portal_url).where(
                    not_deleted(PortalAccount)
                )
            )
        ).all()
        print("portals:", [(r[0], r[1]) for r in rows])
        raise SystemExit(f"portal not found: {PORTAL_NAME}")
    if DEMO_HOST in (official.portal_url or ""):
        raise SystemExit("refusing to bind demo portal URL")
    if PORTAL_URL not in (official.portal_url or ""):
        raise SystemExit(f"portal URL mismatch: {official.portal_url!r}")
    return official


async def ensure_templates(db, portal: PortalAccount) -> dict[str, WorkflowTemplate]:
    found: dict[str, WorkflowTemplate] = {}
    for spec in TEMPLATES:
        template = (
            await db.execute(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.tenant_id == portal.tenant_id,
                    WorkflowTemplate.code == spec["code"],
                    not_deleted(WorkflowTemplate),
                )
            )
        ).scalar_one_or_none()
        if template is None:
            template = WorkflowTemplate(
                tenant_id=portal.tenant_id,
                name=spec["name"],
                code=spec["code"],
                description=spec["name"],
                entity_type="CUSTOMER",
                category=spec["category"],
                status="ENABLED",
                version="1.0.0",
                input_schema=dumps_json(spec["input_schema"]),
                business_steps=dumps_json(spec["business_steps"]),
                created_by=portal.created_by,
            )
            db.add(template)
            await db.flush()
            db.add(
                WorkflowTemplateVersion(
                    template_id=template.id,
                    version=template.version,
                    snapshot=dumps_json(
                        {
                            "code": spec["code"],
                            "name": spec["name"],
                            "inputSchema": spec["input_schema"],
                            "businessSteps": spec["business_steps"],
                        }
                    ),
                    created_by=portal.created_by,
                )
            )
            print("template_insert", spec["code"], spec["name"])
        else:
            if template.name != spec["name"] or (template.description or "") != spec["name"]:
                print(
                    "template_rename",
                    spec["code"],
                    template.name,
                    "->",
                    spec["name"],
                )
                template.name = spec["name"]
                template.description = spec["name"]
            else:
                print("template_keep", spec["code"], spec["name"])
        found[spec["code"]] = template
    return found


def load_publish(path: Path, expected_version: str) -> dict:
    published = json.loads(path.read_text(encoding="utf-8"))
    if published.get("rpaFlowVersion") != expected_version:
        raise SystemExit(
            f"{path.name} version {published.get('rpaFlowVersion')} != {expected_version}"
        )
    return published


async def upsert_binding(db, portal, template, spec, published) -> None:
    checksum = normalize_checksum(published["packageChecksum"]) or ""
    config = {
        "portalUrl": PORTAL_URL,
        "browserSession": BROWSER,
    }
    extra = spec.get("config") or {}
    if extra.get("dryRun") is True:
        config["dryRun"] = True
    if "searches" in extra:
        config["searches"] = extra["searches"]
    if "schedule" in extra:
        config["schedule"] = extra["schedule"]
    binding = (
        await db.execute(
            select(WorkflowBinding).where(
                WorkflowBinding.portal_account_id == portal.id,
                WorkflowBinding.workflow_template_id == template.id,
                not_deleted(WorkflowBinding),
            )
        )
    ).scalar_one_or_none()
    if binding is None:
        binding = WorkflowBinding(
            id=str(uuid.uuid4()),
            portal_account_id=portal.id,
            workflow_template_id=template.id,
            workflow_template_version=template.version or "1.0.0",
            rpa_engine_type="PLAYWRIGHT_CDP",
            rpa_flow_id=published["rpaFlowId"],
            rpa_flow_version=published["rpaFlowVersion"],
            rpa_flow_version_id=published["rpaFlowVersionId"],
            flow_checksum_snapshot=checksum,
            status="ENABLED",
            config=dumps_json(config),
            created_by=portal.created_by,
        )
        db.add(binding)
        print("binding_insert", spec["code"], published["rpaFlowVersion"])
    else:
        binding.rpa_flow_id = published["rpaFlowId"]
        binding.rpa_flow_version = published["rpaFlowVersion"]
        binding.rpa_flow_version_id = published["rpaFlowVersionId"]
        binding.flow_checksum_snapshot = checksum
        binding.status = "ENABLED"
        binding.config = dumps_json(config)
        print("binding_update", spec["code"], published["rpaFlowVersion"])
    parsed = loads_json(binding.config, {})
    print(
        " ",
        "dryRun=" + str(bool(parsed.get("dryRun"))),
        "searches=" + str(bool(parsed.get("searches"))),
        "schedule=" + str((parsed.get("schedule") or {}).get("enabled")),
    )


async def main() -> None:
    async with async_session_factory() as db:
        portal = await find_portal(db)
        print("portal", portal.portal_name, portal.portal_url)
        templates = await ensure_templates(db, portal)
        for spec in BINDINGS:
            published = load_publish(spec["publish"], spec["version"])
            await upsert_binding(db, portal, templates[spec["code"]], spec, published)
        await db.commit()
    await db_engine.dispose()
    print("phase_a_rehearsal_bindings_ready")


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()) or 0)
