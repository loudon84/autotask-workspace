"""Switch 天地伟业 srm_upload_order_attachment Binding to published Flow 1.2.2."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.deps import async_session_factory
from app.models.base import not_deleted
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.rpa_engine_client import normalize_checksum

PORTAL_ID = "b182630d-5023-45c3-ac9c-6b022765b7e1"
TEMPLATE_CODE = "srm_upload_order_attachment"
PUBLISH_JSON = Path(
    r"d:\work_space260811\autotask-workspace\rpa-flows"
    r"\rpa_flow_supplier_portal_upload_order_attachment\_publish_1.2.2.json"
)
ENGINE_URL = "http://127.0.0.1:4610"


async def main() -> None:
    published = json.loads(PUBLISH_JSON.read_text(encoding="utf-8"))
    version = published["rpaFlowVersion"]
    version_id = published["rpaFlowVersionId"]
    checksum = normalize_checksum(published["packageChecksum"]) or ""
    flow_id = published["rpaFlowId"]

    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        resp = await client.post(
            f"{ENGINE_URL}/api/v1/flow-versions/validate-binding",
            headers={
                "X-Actor-Id": "flow-registry-operator",
                "Content-Type": "application/json",
            },
            json={
                "rpaFlowId": flow_id,
                "rpaFlowVersion": version,
                "workflowCode": TEMPLATE_CODE,
            },
        )
        print("validate-binding", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data", payload)
        if not data.get("valid"):
            raise SystemExit(f"binding invalid: {payload}")
        if data.get("rpaFlowVersionId") != version_id:
            raise SystemExit(f"version id mismatch: {data}")

    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(WorkflowBinding, WorkflowTemplate)
                .join(
                    WorkflowTemplate,
                    WorkflowTemplate.id == WorkflowBinding.workflow_template_id,
                )
                .where(
                    WorkflowTemplate.code == TEMPLATE_CODE,
                    not_deleted(WorkflowBinding),
                    not_deleted(WorkflowTemplate),
                )
            )
        ).all()
        if not rows:
            raise SystemExit("no srm_upload_order_attachment bindings found")
        for binding, template in rows:
            print(
                "before",
                binding.id,
                "portal",
                binding.portal_account_id,
                "template",
                template.name,
                "version",
                binding.rpa_flow_version,
                binding.rpa_flow_version_id,
            )
            binding.rpa_flow_id = flow_id
            binding.rpa_flow_version = version
            binding.rpa_flow_version_id = version_id
            binding.flow_checksum_snapshot = checksum
            binding.status = "ENABLED"
            print("after", binding.id, version, version_id, checksum)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
