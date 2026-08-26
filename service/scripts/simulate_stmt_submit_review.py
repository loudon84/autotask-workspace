# -*- coding: utf-8 -*-
"""联调：按对账日期+金额在本地模拟「提交审核成功」，不写 SRM、不派 RPA。

正式演练 Binding dryRun 不点门户「提交审核」，finish 钩子把结果当成未提交，
账单停在待上传发票 / 未对账。本脚本把已有影子账单推进到已完成：
对账状态 CHECKED（已对账）、发票状态 REVIEWING（界面「审批中」）、阶段 STMT_SUBMITTED。
默认预览；加 --yes 才写库。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import ProcessInstanceStatus, ProcessStage, TaskStatus
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.models.statement_bill import StatementBill
from app.services.json_utils import dumps_json, loads_json
from app.services.process_instance_service import (
    PROCESS_CODE_SRM_TIANDI_STATEMENT,
    STMT_SUBMIT_REVIEW_TEMPLATE_CODE,
    STMT_UPLOAD_INVOICE_TEMPLATE_CODE,
    _change_stage,
    _clear_instance_error,
)

ACTOR = "scripts/sim_stmt_submit"
PORTAL_NAME = "天地伟业-芯云-正式演练"
DEFAULT_CHECK_DATE = "2026-04-01"
DEFAULT_CHECK_AMOUNT = "5768205.32"
ALLOWED_STAGES = {
    ProcessStage.STMT_PENDING_INVOICE.value,
    ProcessStage.STMT_PENDING_REVIEW.value,
}
IN_FLIGHT = {
    TaskStatus.QUEUED.value,
    TaskStatus.LEASED.value,
    TaskStatus.RUNNING.value,
    TaskStatus.WAITING_HUMAN.value,
}
CANCEL_TASK_TYPES = {
    STMT_SUBMIT_REVIEW_TEMPLATE_CODE,
    STMT_UPLOAD_INVOICE_TEMPLATE_CODE,
}


def parse_amount(raw: str) -> Decimal:
    text = (
        str(raw or "")
        .replace(",", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("元", "")
        .strip()
    )
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


async def resolve_portal(db, portal_id: str | None) -> PortalAccount:
    query = select(PortalAccount).where(not_deleted(PortalAccount))
    if portal_id:
        query = query.where(PortalAccount.id == portal_id)
    else:
        query = query.where(PortalAccount.portal_name == PORTAL_NAME)
    rows = (await db.execute(query.order_by(PortalAccount.created_at.asc()))).scalars().all()
    if not rows:
        raise SystemExit(f"找不到{PORTAL_NAME} PortalAccount，请传 --portal-id")
    return rows[0]


async def find_bill(
    db, tenant_id: str, check_date: date, amount: Decimal
) -> StatementBill | None:
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


async def cancel_inflight(db, instance_id: str) -> int:
    tasks = (
        await db.execute(
            select(AutomationTask).where(
                AutomationTask.process_instance_id == instance_id,
                AutomationTask.task_type.in_(CANCEL_TASK_TYPES),
                AutomationTask.status.in_(IN_FLIGHT),
                not_deleted(AutomationTask),
            )
        )
    ).scalars().all()
    now = datetime.now(UTC)
    for task in tasks:
        task.status = TaskStatus.CANCELLED.value
        task.deleted_at = now
    return len(tasks)


def mark_drill(instance: ProcessInstance) -> None:
    summary = loads_json(instance.summary, {})
    if not isinstance(summary, dict):
        summary = {}
    drill = summary.get("drill") if isinstance(summary.get("drill"), dict) else {}
    drill.update(
        {
            "uncommitted": True,
            "shadowSubmitReview": True,
            "skippedSrmSubmit": True,
            "step": "srm.stmt.submit_review",
            "blockedAction": "submit_review",
            "at": datetime.now(UTC).isoformat(),
            "note": "本地模拟提交审核成功；未点 SRM 提交、未传 SDMS",
        }
    )
    summary["drill"] = drill
    instance.summary = dumps_json(summary)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="按对账日期+金额在本地模拟提交审核成功（不写 SRM）"
    )
    parser.add_argument(
        "--check-date",
        default=DEFAULT_CHECK_DATE,
        help=f"对账日期 YYYY-MM-DD，默认 {DEFAULT_CHECK_DATE}",
    )
    parser.add_argument(
        "--check-amount",
        default=DEFAULT_CHECK_AMOUNT,
        help=f"对账总额，默认 {DEFAULT_CHECK_AMOUNT}",
    )
    parser.add_argument("--portal-id", default="", help="只处理该门户下的账单")
    parser.add_argument("--yes", action="store_true", help="真正写库；默认只预览")
    args = parser.parse_args()

    check_date = parse_check_date(args.check_date)
    amount = parse_amount(args.check_amount)

    async with async_session_factory() as db:
        portal = await resolve_portal(db, args.portal_id.strip() or None)
        bill = await find_bill(db, portal.tenant_id, check_date, amount)
        print(f"portal={portal.portal_name} id={portal.id}")
        print(f"checkDate={check_date.isoformat()} checkAmount={amount}")
        if bill is None:
            print("未找到本地账单。请先跑 seed_official_unchecked_statement.py，或核对日期/金额/门户。")
            await db_engine.dispose()
            return 1

        instance = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.id == bill.process_instance_id,
                    ProcessInstance.process_code == PROCESS_CODE_SRM_TIANDI_STATEMENT,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one_or_none()
        if instance is None:
            print(f"账单 id={bill.id} 没有对账流程实例")
            await db_engine.dispose()
            return 1

        print(
            f"bill={bill.id} check={bill.check_status} invoice={bill.invoice_status} "
            f"invoiceNo={bill.invoice_no or '—'}"
        )
        print(f"instance={instance.id} stage={instance.stage} status={instance.status}")

        already_done = (
            bill.check_status == "CHECKED"
            and bill.invoice_status == "REVIEWING"
            and instance.stage == ProcessStage.STMT_SUBMITTED.value
        )
        if already_done:
            print("已经是已对账 / 审批中 / 已完成，无需再写。")
            await db_engine.dispose()
            return 0

        if instance.stage not in ALLOWED_STAGES:
            print(
                f"当前阶段 {instance.stage} 不能模拟提交审核"
                f"（需要 STMT_PENDING_INVOICE / STMT_PENDING_REVIEW）"
            )
            await db_engine.dispose()
            return 1

        print(
            "将写入: check_status=CHECKED（已对账） "
            "invoice_status=REVIEWING（审批中） "
            "stage=STMT_SUBMITTED（已完成）"
        )
        print("不点 SRM、不传 SDMS。门户仍是未对账。")
        if not args.yes:
            print("预览模式，未改库。确认后加 --yes，例如:")
            print(
                r"  .\.venv\Scripts\python.exe scripts\simulate_stmt_submit_review.py "
                f"--yes --check-date {check_date.isoformat()} --check-amount {amount}"
            )
            await db_engine.dispose()
            return 0

        cancelled = await cancel_inflight(db, instance.id)
        if cancelled:
            print(f"取消进行中的扫描/提交任务 {cancelled} 条")

        bill.check_status = "CHECKED"
        bill.invoice_status = "REVIEWING"
        bill.last_error = None
        instance.status = ProcessInstanceStatus.COMPLETED.value
        _clear_instance_error(instance)
        _change_stage(
            db,
            instance,
            ProcessStage.STMT_SUBMITTED,
            actor=ACTOR,
            note="脚本模拟提交审核成功；未点 SRM、未传 SDMS",
        )
        mark_drill(instance)
        await db.commit()
        await db.refresh(bill)
        await db.refresh(instance)
        print(
            f"完成 bill={bill.id} check={bill.check_status} invoice={bill.invoice_status} "
            f"stage={instance.stage} status={instance.status}"
        )
        print("Client 刷新后应到「已完成」。SRM 仍是未对账。")
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
