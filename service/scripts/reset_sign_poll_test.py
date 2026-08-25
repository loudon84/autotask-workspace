# -*- coding: utf-8 -*-
"""把 POJS2607240005 实例退回待回签（SIGN_REQUESTED）并清错误，便于重测回签轮询归档。

默认预览；加 --yes 才写库。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.enums import ProcessInstanceStatus, ProcessStage
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.services.json_utils import dumps_json, loads_json
from app.services.process_instance_service import PROCESS_CODE_SRM_CUSTOMER_ORDER

PO_NO = "POJS2607240005"
PORTAL_NAME = "天地伟业-国际test"


async def main() -> int:
    parser = argparse.ArgumentParser(description="退回待回签以重测归档兜底工号")
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
        instance = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.portal_account_id == portal.id,
                    ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
                    ProcessInstance.biz_key == PO_NO,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one_or_none()
        if instance is None:
            print(f"在门户 {PORTAL_NAME} 下找不到实例 {PO_NO}")
            await db_engine.dispose()
            return 1

        print(f"before: id={instance.id} stage={instance.stage} status={instance.status}")
        print(f"  error_code={getattr(instance, 'error_code', None)} error_message={getattr(instance, 'error_message', None)}")

        summary = loads_json(instance.summary, {})
        summary["sdmsUsername"] = ""
        new_summary = dumps_json(summary)

        print(f"after : stage={ProcessStage.SIGN_REQUESTED.value} status={ProcessInstanceStatus.ACTIVE.value}")
        print(f"  error cleared, summary.sdmsUsername cleared")
        if not args.yes:
            print("预览模式，未写库。确认后加 --yes")
            await db_engine.dispose()
            return 0

        instance.stage = ProcessStage.SIGN_REQUESTED.value
        instance.status = ProcessInstanceStatus.ACTIVE.value
        instance.error_code = None
        instance.error_message = None
        instance.summary = new_summary
        await db.commit()
        print("已写库。下次回签轮询将重新探测并触发归档（用兜底工号 SMC-SZ-HR15563）。")
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
