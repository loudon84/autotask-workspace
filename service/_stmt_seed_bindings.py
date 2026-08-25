"""Insert 天地伟业 statement templates + bindings from Engine publish JSON."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from sqlalchemy import select

from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json
from app.services.rpa_engine_client import normalize_checksum

TENANT_ID = "2be7c618-326d-4a73-91ea-1cfda10f7073"
PORTAL_ID = "b182630d-5023-45c3-ac9c-6b022765b7e1"
ACTOR_ID = "8468ef67-e4d6-4efd-bc41-ca5189449b09"
PUBLISH_JSON = Path(
    r"d:\work_space260811\autotask-workspace\rpa-engine\runtime-cache\statement-flow-publish.json"
)
CONFIG = dumps_json(
    {
        "portalUrl": "http://192.168.102.247:3000",
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
TEMPLATES = [
    {
        "code": "srm_stmt_query_receipts",
        "name": "天地伟业·收货列表查询",
        "flow": "rpa_flow_srm_stmt_query_receipts",
        "input": [
            {"name": "dateStart", "label": "入库确认开始日期", "type": "string", "required": True},
            {"name": "dateEnd", "label": "入库确认结束日期", "type": "string", "required": True},
        ],
        "steps": [
            {"id": "srm.login", "name": "登录门户", "type": "srm.login"},
            {"id": "srm.query_receipts", "name": "查询收货列表", "type": "srm.query_receipts"},
        ],
    },
    {
        "code": "srm_stmt_generate",
        "name": "天地伟业·生成对账单",
        "flow": "rpa_flow_srm_stmt_generate",
        "input": [
            {"name": "lines", "label": "勾选行", "type": "array", "required": True},
        ],
        "steps": [
            {"id": "srm.login", "name": "登录门户", "type": "srm.login"},
            {"id": "srm.generate_statement", "name": "生成对账单", "type": "srm.generate_statement"},
        ],
    },
    {
        "code": "srm_stmt_upload_invoice",
        "name": "天地伟业·上传对账发票",
        "flow": "rpa_flow_srm_stmt_upload_invoice",
        "input": [
            {"name": "checkDate", "label": "对账日期", "type": "string", "required": True},
            {"name": "checkAmount", "label": "对账金额", "type": "number", "required": True},
        ],
        "steps": [
            {"id": "srm.login", "name": "登录门户", "type": "srm.login"},
            {"id": "srm.upload_invoice", "name": "扫描上传发票", "type": "srm.upload_invoice"},
        ],
    },
    {
        "code": "srm_stmt_submit_review",
        "name": "天地伟业·提交对账审核",
        "flow": "rpa_flow_srm_stmt_submit_review",
        "input": [
            {"name": "checkDate", "label": "对账日期", "type": "string", "required": True},
            {"name": "checkAmount", "label": "对账金额", "type": "number", "required": True},
            {"name": "filePaths", "label": "发票文件路径", "type": "array", "required": True},
        ],
        "steps": [
            {"id": "srm.login", "name": "登录门户", "type": "srm.login"},
            {"id": "srm.upload_invoice", "name": "扫描上传发票", "type": "srm.upload_invoice"},
            {"id": "srm.submit_review", "name": "提交审核", "type": "srm.submit_review"},
        ],
    },
]


async def main() -> None:
    published = {item["rpaFlowId"]: item for item in json.loads(PUBLISH_JSON.read_text(encoding="utf-8"))}
    from app.core.deps import async_session_factory

    async with async_session_factory() as db:
        for spec in TEMPLATES:
            flow = published[spec["flow"]]
            template = (
                await db.execute(
                    select(WorkflowTemplate).where(
                        WorkflowTemplate.tenant_id == TENANT_ID,
                        WorkflowTemplate.code == spec["code"],
                    )
                )
            ).scalar_one_or_none()
            if template is None:
                template = WorkflowTemplate(
                    id=str(uuid.uuid4()),
                    tenant_id=TENANT_ID,
                    name=spec["name"],
                    code=spec["code"],
                    description=spec["name"],
                    entity_type="CUSTOMER",
                    category="statement",
                    status="ENABLED",
                    version="1.0.0",
                    input_schema=dumps_json(spec["input"]),
                    business_steps=dumps_json(spec["steps"]),
                    created_by=ACTOR_ID,
                )
                db.add(template)
                await db.flush()
                print("template_insert", spec["code"], template.id)
            else:
                template.input_schema = dumps_json(spec["input"])
                template.business_steps = dumps_json(spec["steps"])
                print("template_exists", spec["code"], template.id)
            binding = (
                await db.execute(
                    select(WorkflowBinding).where(
                        WorkflowBinding.portal_account_id == PORTAL_ID,
                        WorkflowBinding.workflow_template_id == template.id,
                    )
                )
            ).scalar_one_or_none()
            checksum = normalize_checksum(flow["packageChecksum"]) or ""
            if binding is None:
                binding = WorkflowBinding(
                    id=str(uuid.uuid4()),
                    portal_account_id=PORTAL_ID,
                    workflow_template_id=template.id,
                    workflow_template_version="1.0.0",
                    rpa_engine_type="PLAYWRIGHT_CDP",
                    rpa_flow_id=flow["rpaFlowId"],
                    rpa_flow_version=flow["rpaFlowVersion"],
                    rpa_flow_version_id=flow["rpaFlowVersionId"],
                    flow_checksum_snapshot=checksum,
                    status="ENABLED",
                    config=CONFIG,
                    created_by=ACTOR_ID,
                )
                db.add(binding)
                print("binding_insert", spec["code"], binding.id)
            else:
                binding.rpa_flow_id = flow["rpaFlowId"]
                binding.rpa_flow_version = flow["rpaFlowVersion"]
                binding.rpa_flow_version_id = flow["rpaFlowVersionId"]
                binding.flow_checksum_snapshot = checksum
                binding.status = "ENABLED"
                binding.config = CONFIG
                print("binding_update", spec["code"], binding.id)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
