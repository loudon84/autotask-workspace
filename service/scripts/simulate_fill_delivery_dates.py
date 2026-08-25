# -*- coding: utf-8 -*-
"""联调：按客户订单号在本地模拟「填写交货日期」，不写 SRM、不派 RPA。

正式演练没有填交期 Binding，门户也没有待签章保存按钮。
本脚本把已有流程实例的订单行写成已写入，并推进到待签章（DATES_COMPLETE）。
默认预览；加 --yes 才写库。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import ProcessInstanceStatus, ProcessLineStatus, ProcessStage, TaskStatus
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.models.process_line_item import ProcessLineItem
from app.services.json_utils import dumps_json, loads_json
from app.services.process_instance_service import (
    FILL_LINE_DATE_TEMPLATE_CODE,
    PROCESS_CODE_SRM_CUSTOMER_ORDER,
    _change_stage,
    _clear_instance_error,
    _valid_date,
    list_line_items,
)

ACTOR = "scripts/sim_fill_dates"
DEFAULT_PO = "POJS2607170008"
ALLOWED_STAGES = {
    ProcessStage.SDMS_CREATED.value,
    ProcessStage.DATES_PARTIAL.value,
    ProcessStage.DATES_COMPLETE.value,
}
IN_FLIGHT = {
    TaskStatus.QUEUED.value,
    TaskStatus.LEASED.value,
    TaskStatus.RUNNING.value,
    TaskStatus.WAITING_HUMAN.value,
}


def resolve_line_date(line: ProcessLineItem, override: str | None) -> str:
    if override:
        return override
    request = str(line.request_date or "").strip()
    if _valid_date(request):
        return request
    return date.today().isoformat()


def mark_drill(instance: ProcessInstance, date_note: str) -> None:
    summary = loads_json(instance.summary, {})
    if not isinstance(summary, dict):
        summary = {}
    drill = summary.get("drill") if isinstance(summary.get("drill"), dict) else {}
    drill.update(
        {
            "uncommitted": True,
            "shadowFillDates": True,
            "skippedSrmSave": True,
            "step": "srm.fill_line_delivery_date",
            "blockedAction": None,
            "at": datetime.now(UTC).isoformat(),
            "note": date_note,
        }
    )
    summary["drill"] = drill
    instance.summary = dumps_json(summary)


async def find_instances(
    db,
    po_nos: list[str],
    portal_id: str | None,
) -> list[tuple[ProcessInstance, PortalAccount]]:
    query = (
        select(ProcessInstance, PortalAccount)
        .join(PortalAccount, PortalAccount.id == ProcessInstance.portal_account_id)
        .where(
            ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
            ProcessInstance.biz_key.in_(po_nos),
            not_deleted(ProcessInstance),
            not_deleted(PortalAccount),
        )
    )
    if portal_id:
        query = query.where(ProcessInstance.portal_account_id == portal_id)
    rows = (
        await db.execute(query.order_by(ProcessInstance.biz_key.asc(), ProcessInstance.created_at.desc()))
    ).all()
    return [(inst, portal) for inst, portal in rows]


async def cancel_inflight_fill_tasks(db, instance_id: str) -> int:
    tasks = (
        await db.execute(
            select(AutomationTask).where(
                AutomationTask.process_instance_id == instance_id,
                AutomationTask.task_type == FILL_LINE_DATE_TEMPLATE_CODE,
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


async def apply_one(
    db,
    instance: ProcessInstance,
    override_date: str | None,
) -> list[str]:
    logs: list[str] = []
    lines = await list_line_items(db, instance.id)
    if not lines:
        raise SystemExit(
            f"{instance.biz_key} 没有订单行。请等「建 SDMS 销售订单」成功后再跑。"
        )
    if instance.stage not in ALLOWED_STAGES:
        raise SystemExit(
            f"{instance.biz_key} 当前阶段 {instance.stage} 不能模拟填交期"
            f"（需要 SDMS_CREATED / DATES_PARTIAL / DATES_COMPLETE）"
        )

    cancelled = await cancel_inflight_fill_tasks(db, instance.id)
    if cancelled:
        logs.append(f"  取消进行中的填交期任务 {cancelled} 条")

    for line in lines:
        expected = resolve_line_date(line, override_date)
        logs.append(
            f"  行 {line.line_number} {line.line_status}"
            f" {line.expected_delivery_date or '—'} -> {expected} WRITTEN"
        )
        line.expected_delivery_date = expected
        line.line_status = ProcessLineStatus.WRITTEN.value
        line.last_error_code = None
        line.last_error_message = None
        line.sub_task_id = None

    instance.status = ProcessInstanceStatus.ACTIVE.value
    instance.line_total = len(lines)
    instance.line_done = len(lines)
    _clear_instance_error(instance)
    _change_stage(
        db,
        instance,
        ProcessStage.DATES_COMPLETE,
        actor=ACTOR,
        note="脚本模拟填交期成功；未写 SRM、未派 RPA",
    )
    date_note = (
        f"本地模拟全部 {len(lines)} 行已写入；SRM 未保存。"
        + (f" 统一日期 {override_date}。" if override_date else " 日期优先用要求交货日期。")
    )
    mark_drill(instance, date_note)
    logs.append(f"  阶段 -> DATES_COMPLETE 已写入 {instance.line_done}/{instance.line_total}")
    return logs


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="按客户订单号在本地模拟填写交货日期（不写 SRM）"
    )
    parser.add_argument(
        "po_nos",
        nargs="*",
        default=[DEFAULT_PO],
        metavar="PO",
        help=f"采购订单号，可多个；默认 {DEFAULT_PO}",
    )
    parser.add_argument("--portal-id", default="", help="只处理该门户下的实例")
    parser.add_argument(
        "--date",
        default="",
        help="全部行使用该 YYYY-MM-DD；不传则用行上要求交货日期，再不行用今天",
    )
    parser.add_argument("--yes", action="store_true", help="真正写库；默认只预览")
    args = parser.parse_args()
    po_nos = [str(item).strip().upper() for item in args.po_nos if str(item).strip()]
    if not po_nos:
        po_nos = [DEFAULT_PO]
    override = str(args.date).strip()
    if override and not _valid_date(override):
        raise SystemExit("--date 必须是 YYYY-MM-DD")

    async with async_session_factory() as db:
        pairs = await find_instances(db, po_nos, args.portal_id.strip() or None)
        found = {inst.biz_key for inst, _portal in pairs}
        missing = [po for po in po_nos if po not in found]
        print(f"单号: {', '.join(po_nos)}")
        if override:
            print(f"统一日期: {override}")
        if missing:
            print(f"未找到实例: {', '.join(missing)}")
        if not pairs:
            await db_engine.dispose()
            return 1

        print("将处理:")
        for inst, portal in pairs:
            lines = await list_line_items(db, inst.id)
            print(
                f"  {inst.biz_key} portal={portal.portal_name} "
                f"id={inst.id[:8]}… {inst.stage}/{inst.status} "
                f"lines={len(lines)} done={inst.line_done}/{inst.line_total}"
            )
            for line in lines:
                expected = resolve_line_date(line, override or None)
                print(
                    f"    行 {line.line_number} {line.line_status} "
                    f"要求={line.request_date or '—'} "
                    f"预计={line.expected_delivery_date or '—'} -> {expected}"
                )

        if not args.yes:
            print()
            print("预览模式，未改库。确认执行请加 --yes，例如:")
            print(
                r"  .\.venv\Scripts\python.exe scripts\simulate_fill_delivery_dates.py "
                f"--yes {' '.join(po_nos)}"
            )
            await db_engine.dispose()
            return 0

        print()
        print("开始本地模拟填交期（不写 SRM）…")
        for inst, _portal in pairs:
            print(inst.biz_key)
            for line in await apply_one(db, inst, override or None):
                print(line)
        await db.commit()
        print("完成。Client 刷新后应到「待签章」。SRM 不会有交期。")
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
