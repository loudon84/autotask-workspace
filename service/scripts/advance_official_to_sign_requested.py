"""把正式演练样例单推进到待回签，供回签轮询认已回签。

不点 SRM 填交期/签章。默认预览，加 --yes 才写库。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.enums import ProcessInstanceStatus, ProcessStage
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json, loads_json
from app.services.process_instance_service import (
    PROCESS_CODE_SRM_CUSTOMER_ORDER,
    _change_stage,
    _clear_instance_error,
)

OFFICIAL_PORTAL_NAME = "天地伟业-国际-正式演练"
DEFAULT_PO = "POJS2607170008"
ACTOR = "scripts/advance_official_to_sign_requested"
CHECK_CODES = ("srm_check_reply_status", "srm_upload_order_attachment")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("po_no", nargs="?", default=DEFAULT_PO)
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    po_no = str(args.po_no).strip().upper()

    async with async_session_factory() as db:
        portal = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == OFFICIAL_PORTAL_NAME,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one()
        inst = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.portal_account_id == portal.id,
                    ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
                    ProcessInstance.biz_key == po_no,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one_or_none()
        if inst is None:
            raise SystemExit(f"instance not found: {po_no}")
        print("before", inst.id, inst.status, inst.stage, inst.line_total, inst.line_done)
        bindings = (
            await db.execute(
                select(WorkflowTemplate.code, WorkflowBinding.rpa_flow_version)
                .join(
                    WorkflowBinding,
                    WorkflowBinding.workflow_template_id == WorkflowTemplate.id,
                )
                .where(
                    WorkflowBinding.portal_account_id == portal.id,
                    not_deleted(WorkflowBinding),
                    not_deleted(WorkflowTemplate),
                    WorkflowTemplate.code.in_(CHECK_CODES),
                )
            )
        ).all()
        bound = {code: version for code, version in bindings}
        for code in CHECK_CODES:
            print("binding", code, bound.get(code) or "MISSING")

        if not args.yes:
            print("preview only; pass --yes to write")
            await db_engine.dispose()
            return 0

        inst.status = ProcessInstanceStatus.ACTIVE.value
        _clear_instance_error(inst)
        _change_stage(
            db,
            inst,
            ProcessStage.SIGN_REQUESTED,
            actor=ACTOR,
            note="正式演练跳过填交期/签章，待回签轮询认已回签",
        )
        summary = loads_json(inst.summary, {})
        if not isinstance(summary, dict):
            summary = {}
        drill = summary.get("drill") if isinstance(summary.get("drill"), dict) else {}
        drill.update(
            {
                "uncommitted": True,
                "skippedFillSign": True,
                "step": "srm.check_reply_status",
                "blockedAction": None,
                "at": datetime.now(UTC).isoformat(),
                "note": "正式站该单已回签，无交期/保存/签章控件；跳到待回签由轮询探测",
            }
        )
        summary["drill"] = drill
        inst.summary = dumps_json(summary)
        await db.commit()
        print("after", inst.status, inst.stage)
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
