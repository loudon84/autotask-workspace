# -*- coding: utf-8 -*-
"""v4.0 演练：把正式站样例 PO 当成扫单待签章，创建客户订单并排队建 SDMS。

默认预览；加 --yes 才写库。不调 SRM、不写凭据。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.services.json_utils import dumps_json, loads_json
from app.services.process_instance_service import (
    PROCESS_CODE_SRM_CUSTOMER_ORDER,
    create_from_scan,
)

DEFAULT_PO = "POJS2607170008"
ACTOR = "scripts/seed_tiandi_drill"


async def resolve_portal(db, portal_id: str | None) -> PortalAccount:
    query = select(PortalAccount).where(not_deleted(PortalAccount))
    if portal_id:
        query = query.where(PortalAccount.id == portal_id)
    else:
        query = query.where(PortalAccount.portal_name == "天地伟业-国际-正式演练")
    rows = (await db.execute(query.order_by(PortalAccount.created_at.asc()))).scalars().all()
    if not rows:
        raise SystemExit("找不到天地伟业-国际-正式演练 PortalAccount，请传 --portal-id")
    return rows[0]


async def find_instance(db, portal_id: str, po_no: str) -> ProcessInstance | None:
    return (
        await db.execute(
            select(ProcessInstance).where(
                ProcessInstance.portal_account_id == portal_id,
                ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
                ProcessInstance.biz_key == po_no,
                not_deleted(ProcessInstance),
            )
        )
    ).scalar_one_or_none()


def mark_drill(instance: ProcessInstance, po_no: str) -> None:
    summary = loads_json(instance.summary, {})
    if not isinstance(summary, dict):
        summary = {}
    summary["poNo"] = po_no
    summary["drill"] = {
        "uncommitted": False,
        "shadow": True,
        "assumedPending": True,
        "step": "srm.scan_pending_orders",
        "blockedAction": None,
        "at": datetime.now(UTC).isoformat(),
        "note": "正式站无待签章，演练把此单当成待签章扫入",
    }
    instance.summary = dumps_json(summary)


async def main() -> int:
    parser = argparse.ArgumentParser(description="把正式站样例 PO 扫成客户订单并排队建 SDMS")
    parser.add_argument("po_no", nargs="?", default=DEFAULT_PO)
    parser.add_argument("--portal-id", default="")
    parser.add_argument("--yes", action="store_true", help="真正写库；默认只预览")
    args = parser.parse_args()
    po_no = str(args.po_no).strip().upper()

    async with async_session_factory() as db:
        portal = await resolve_portal(db, args.portal_id.strip() or None)
        existing = await find_instance(db, portal.id, po_no)
        print(f"portal={portal.portal_name} id={portal.id}")
        print(f"portalUrl={portal.portal_url}")
        print(f"login={portal.login_account}")
        print(f"po={po_no}")
        if existing is not None:
            print(f"已存在实例 id={existing.id} stage={existing.stage} status={existing.status}")
            print("不会重复创建。")
            await db_engine.dispose()
            return 0
        print("将执行 create_from_scan：阶段 CREATING_SDMS，并排队「1. 建 SDMS 销售订单」")
        if not args.yes:
            print("预览模式，未写库。确认后加 --yes")
            await db_engine.dispose()
            return 0
        created = await create_from_scan(
            db,
            portal.tenant_id,
            portal.id,
            [
                {
                    "poNo": po_no,
                    "orderDate": "2026-07-17",
                    "orderType": "普通订单",
                    "totalAmount": "36867287.81",
                    "replyStatus": "待签章",
                    "deliveryStatus": "未发货",
                    "supplierName": portal.erp_entity_name,
                }
            ],
            actor=ACTOR,
            commit=False,
            allow_missing_prepare_binding=True,
        )
        if not created:
            print("create_from_scan 未创建（可能并发已存在）")
            await db.rollback()
            await db_engine.dispose()
            return 1
        instance = created[0]
        mark_drill(instance, po_no)
        await db.commit()
        task = (
            await db.execute(
                select(AutomationTask)
                .where(
                    AutomationTask.process_instance_id == instance.id,
                    not_deleted(AutomationTask),
                )
                .order_by(AutomationTask.created_at.desc())
            )
        ).scalars().first()
        print(f"created instance={instance.id} stage={instance.stage}")
        if task is not None:
            print(f"queued task={task.id} type={task.task_type} status={task.status.value if hasattr(task.status, 'value') else task.status}")
        print(json.dumps(loads_json(instance.summary, {}), ensure_ascii=False))
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
