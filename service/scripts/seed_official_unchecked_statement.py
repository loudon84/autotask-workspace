# -*- coding: utf-8 -*-
"""v4.0 演练：把正式站已有未对账写成本地待上传发票影子账单。

生成演练 dryRun 不会在门户落下对账单，不能拿那张待生成草稿去上传发票。
本脚本按门户真实未对账的「对账日期 + 对账总额」插入本地账单，阶段为待上传发票。
默认预览；加 --yes 才写库。不调 SRM、不写凭据。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.enums import ProcessInstanceStatus, ProcessStage
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.models.statement_bill import StatementBill
from app.services.json_utils import dumps_json, loads_json
from app.services.process_instance_service import PROCESS_CODE_SRM_TIANDI_STATEMENT

ACTOR = "scripts/seed_stmt_unchecked"  # created_by varchar(36)


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


def parse_amount(raw: str) -> Decimal:
    text = str(raw or "").replace(",", "").replace("¥", "").replace("￥", "").replace("元", "").strip()
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise SystemExit(f"对账总额无效: {raw!r}") from exc


def parse_check_date(raw: str) -> date:
    text = str(raw or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit("对账日期必须是 YYYY-MM-DD") from exc


def biz_key_for(check_date: date, amount: Decimal) -> str:
    return f"{check_date.isoformat()}|{amount}"


async def find_bill(db, tenant_id: str, check_date: date, amount: Decimal) -> StatementBill | None:
    return (
        await db.execute(
            select(StatementBill).where(
                StatementBill.tenant_id == tenant_id,
                StatementBill.check_date == check_date,
                StatementBill.check_amount == amount,
                not_deleted(StatementBill),
            )
        )
    ).scalar_one_or_none()


async def find_instance(db, portal_id: str, biz_key: str) -> ProcessInstance | None:
    return (
        await db.execute(
            select(ProcessInstance).where(
                ProcessInstance.portal_account_id == portal_id,
                ProcessInstance.process_code == PROCESS_CODE_SRM_TIANDI_STATEMENT,
                ProcessInstance.biz_key == biz_key,
                not_deleted(ProcessInstance),
            )
        )
    ).scalar_one_or_none()


def drill_summary(*, check_date: date, amount: Decimal, sdms_check_num: str) -> dict:
    payload = {
        "local_amount": str(amount),
        "drill": {
            "uncommitted": False,
            "shadow": True,
            "step": "srm.stmt.unchecked_shadow",
            "blockedAction": None,
            "at": datetime.now(UTC).isoformat(),
            "note": "正式站已有未对账；生成演练未点门户，用这条当生成后替身",
        },
    }
    if sdms_check_num:
        payload["sdms_check_num"] = sdms_check_num
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="把正式站已有未对账写成本地待上传发票影子账单")
    parser.add_argument("--check-date", required=True, help="门户未对账行的对账日期 YYYY-MM-DD")
    parser.add_argument("--check-amount", required=True, help="门户未对账行的对账总额")
    parser.add_argument("--portal-id", default="")
    parser.add_argument("--sdms-check-num", default="", help="可选；演练提交不传 SDMS")
    parser.add_argument("--yes", action="store_true", help="真正写库；默认只预览")
    args = parser.parse_args()

    check_date = parse_check_date(args.check_date)
    amount = parse_amount(args.check_amount)
    biz_key = biz_key_for(check_date, amount)

    async with async_session_factory() as db:
        portal = await resolve_portal(db, args.portal_id.strip() or None)
        existing_bill = await find_bill(db, portal.tenant_id, check_date, amount)
        existing_instance = await find_instance(db, portal.id, biz_key)
        print(f"portal={portal.portal_name} id={portal.id}")
        print(f"portalUrl={portal.portal_url}")
        print(f"login={portal.login_account}")
        print(f"checkDate={check_date.isoformat()} checkAmount={amount}")
        print(f"bizKey={biz_key}")
        if existing_bill is not None:
            print(
                f"已存在账单 id={existing_bill.id} "
                f"status={existing_bill.check_status} "
                f"instance={existing_bill.process_instance_id}"
            )
            print("不会重复创建。")
            await db_engine.dispose()
            return 0
        if existing_instance is not None:
            print(f"已存在实例 id={existing_instance.id} stage={existing_instance.stage}")
            print("不会重复创建。")
            await db_engine.dispose()
            return 0
        print("将创建 statement_bills UNCHECKED + 流程阶段 STMT_PENDING_INVOICE（待上传发票）")
        if not args.yes:
            print("预览模式，未写库。确认后加 --yes")
            await db_engine.dispose()
            return 0

        instance = ProcessInstance(
            tenant_id=portal.tenant_id,
            process_code=PROCESS_CODE_SRM_TIANDI_STATEMENT,
            biz_key=biz_key,
            title=f"对账单 {check_date.isoformat()} / {amount}",
            portal_account_id=portal.id,
            stage=ProcessStage.STMT_PENDING_INVOICE.value,
            status=ProcessInstanceStatus.ACTIVE.value,
            line_total=0,
            line_done=0,
            summary=dumps_json(drill_summary(
                check_date=check_date,
                amount=amount,
                sdms_check_num=str(args.sdms_check_num or "").strip(),
            )),
            created_by=ACTOR,
        )
        db.add(instance)
        await db.flush()
        bill = StatementBill(
            tenant_id=portal.tenant_id,
            process_instance_id=instance.id,
            portal_account_id=portal.id,
            check_date=check_date,
            check_amount=amount,
            check_status="UNCHECKED",
            invoice_status="NOT_UPLOADED",
            last_error=None,
            created_by=ACTOR,
        )
        db.add(bill)
        await db.commit()
        await db.refresh(instance)
        await db.refresh(bill)
        print(f"created bill={bill.id} instance={instance.id} stage={instance.stage}")
        print(json.dumps(loads_json(instance.summary, {}), ensure_ascii=False))
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
