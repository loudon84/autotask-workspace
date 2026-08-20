# -*- coding: utf-8 -*-
"""为天地伟业-国际test 创建一条待回签（SIGN_REQUESTED）客户订单实例，用于测试回签轮询。

默认预览；加 --yes 才写库。不调 SRM、不写凭据、不排队建单任务。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.enums import ProcessInstanceStatus, ProcessLineStatus, ProcessStage
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.models.process_line_item import ProcessLineItem
from app.services.json_utils import dumps_json
from app.services.process_instance_service import PROCESS_CODE_SRM_CUSTOMER_ORDER

PORTAL_NAME = "天地伟业-国际test"
PO_NO = "POJS2607240005"
ACTOR = "scripts/seed_sign_poll_test"


async def main() -> int:
    parser = argparse.ArgumentParser(description="为国际test创建待回签实例以测试回签轮询")
    parser.add_argument("--yes", action="store_true", help="真正写库；默认只预览")
    args = parser.parse_args()

    async with async_session_factory() as db:
        portal = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == PORTAL_NAME,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
        if portal is None:
            print(f"找不到门户 {PORTAL_NAME}")
            await db_engine.dispose()
            return 1
        print(f"portal={portal.portal_name} id={portal.id}")
        print(f"  businessEntity={portal.business_entity} ou={portal.ou}")
        print(f"  erp_entity_name={portal.erp_entity_name}")

        existing = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.portal_account_id == portal.id,
                    ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
                    ProcessInstance.biz_key == PO_NO,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            print(f"已存在实例 id={existing.id} stage={existing.stage} status={existing.status}")
            print("不会重复创建。")
            await db_engine.dispose()
            return 0

        instance_id = str(uuid.uuid4())
        summary = {
            "poNo": PO_NO,
            "orderNumber": "10108260800009",
            "headerId": "1100990",
            "supplierCode": portal.erp_entity_code,
            "supplierName": portal.erp_entity_name,
            "sdmsUsername": "",
        }
        print(f"将创建实例 po={PO_NO} stage=SIGN_REQUESTED（待回签）")
        print(f"  summary={dumps_json(summary)}")
        if not args.yes:
            print("预览模式，未写库。确认后加 --yes")
            await db_engine.dispose()
            return 0

        instance = ProcessInstance(
            id=instance_id,
            tenant_id=portal.tenant_id,
            process_code=PROCESS_CODE_SRM_CUSTOMER_ORDER,
            biz_key=PO_NO,
            title=f"{portal.portal_name}·客户订单 - {PO_NO}",
            portal_account_id=portal.id,
            stage=ProcessStage.SIGN_REQUESTED.value,
            status=ProcessInstanceStatus.ACTIVE.value,
            line_total=2,
            line_done=2,
            summary=dumps_json(summary),
            created_by=ACTOR,
        )
        db.add(instance)
        await db.flush()

        lines = [
            ProcessLineItem(
                id=str(uuid.uuid4()),
                instance_id=instance_id,
                line_number="10",
                material_number="1B.30040.020262",
                item_name="芯片-视",
                item_specification="规格A",
                order_quantity="100",
                order_quantity_uom="PCS",
                unit_selling_price="1.50",
                tax_included_amount="169.50",
                request_date="2026-08-20",
                standard_delivery_days="7",
                expected_delivery_date="2026-08-25",
                line_status=ProcessLineStatus.WRITTEN.value,
            ),
            ProcessLineItem(
                id=str(uuid.uuid4()),
                instance_id=instance_id,
                line_number="20",
                material_number="1B.30040.020263",
                item_name="芯片-视-2",
                item_specification="规格B",
                order_quantity="200",
                order_quantity_uom="PCS",
                unit_selling_price="2.50",
                tax_included_amount="565.00",
                request_date="2026-08-20",
                standard_delivery_days="7",
                expected_delivery_date="2026-08-25",
                line_status=ProcessLineStatus.WRITTEN.value,
            ),
        ]
        for line in lines:
            db.add(line)
        await db.commit()
        print(f"created instance={instance.id} stage={instance.stage} status={instance.status}")
        print("回签轮询候选已就绪：在 Client 流程实例列表点「立即回签轮询」即可触发探测。")
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
