# -*- coding: utf-8 -*-
"""联调用：硬删「天地伟业对账单」SOP 数据，便于重新填单/生成。

================================================================================
用途
--------------------------------------------------------------------------------
对账单联调时，把本系统创建的对账单草稿/实例整树删掉，避免
(tenant + check_date + check_amount) 唯一约束挡住再次生成。

只动 process_code = srm_tiandi_statement，以及 4 个对账单子任务类型。
不会删客户订单流程实例。

支持：
- 全量清空对账单 SOP（不传 id）
- 按对账单 id 只删指定单据（传一个或多个 UUID）

================================================================================
会删什么（硬删，不可恢复）
--------------------------------------------------------------------------------
1) 范围内 statement_bills
2) 对应 process_instances（仅 srm_tiandi_statement）及 process_stage_history
3) 这些实例上的 automation_tasks，以及关联 Run/事件/步骤/制品/租约/人工动作
4) 全量模式下：未挂实例的「查询收货」等对账单临时任务（填单页搜索产生）

不会动：
- 客户订单 process_instances（srm_customer_order）
- workflow_templates / workflow_bindings / portal_accounts
- rpa_engine Flow Registry、MinIO 包

================================================================================
怎么执行（在 service 目录）
--------------------------------------------------------------------------------
  cd d:\\work_space260811\\autotask-workspace\\service

  # 全量：只预览
  .\\.venv\\Scripts\\python.exe scripts\\clear_statement_bills.py

  # 全量：确认删除
  .\\.venv\\Scripts\\python.exe scripts\\clear_statement_bills.py --yes

  # 指定对账单 id：预览
  .\\.venv\\Scripts\\python.exe scripts\\clear_statement_bills.py <bill-id>

  # 指定对账单 id（可多个）：确认删除
  .\\.venv\\Scripts\\python.exe scripts\\clear_statement_bills.py --yes <bill-id> <bill-id2>

依赖：
- service/.env 里的 DATABASE_URL（postgresql+asyncpg://...）
- 本机已装 asyncpg（service/.venv 里一般有）

================================================================================
注意
--------------------------------------------------------------------------------
- 这是联调重置脚本，不是产品能力；生产环境不要跑。
- 不要用 clear_process_instances.py --yes 来清对账单：那会把客户订单一起删掉。
- 跑之前建议停一下正在执行的对账单任务，或接受 Run 可能报错。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from clear_process_instances import (  # noqa: E402
    _delete_where_in,
    _table_exists,
    collect_linked_task_ids,
    hard_clear,
    load_dsn,
)

PROCESS_CODE = "srm_tiandi_statement"
STMT_TASK_TYPES = [
    "srm_stmt_query_receipts",
    "srm_stmt_generate",
    "srm_stmt_upload_invoice",
    "srm_stmt_submit_review",
]


async def resolve_bill_rows(
    conn: asyncpg.Connection,
    bill_ids: list[str] | None,
) -> list[asyncpg.Record]:
    if not await _table_exists(conn, "statement_bills"):
        print("表 statement_bills 不存在，可能尚未执行迁移 c4a1f0e82b17。")
        return []
    if bill_ids:
        rows = await conn.fetch(
            """
            SELECT id, process_instance_id, check_date, check_amount, check_status
            FROM statement_bills
            WHERE id = ANY($1::text[])
            ORDER BY created_at DESC
            """,
            bill_ids,
        )
        found = {r["id"] for r in rows}
        missing = [i for i in bill_ids if i not in found]
        if missing:
            print(f"未找到对账单: {', '.join(missing)}")
        return list(rows)
    return list(
        await conn.fetch(
            """
            SELECT id, process_instance_id, check_date, check_amount, check_status
            FROM statement_bills
            ORDER BY created_at DESC
            """
        )
    )


async def resolve_instance_ids(
    conn: asyncpg.Connection,
    bill_ids: list[str] | None,
) -> list[str]:
    bill_rows = await resolve_bill_rows(conn, bill_ids)
    from_bills = [r["process_instance_id"] for r in bill_rows if r["process_instance_id"]]
    if bill_ids:
        instance_ids = list(dict.fromkeys(from_bills))
    else:
        extra = [
            r["id"]
            for r in await conn.fetch(
                """
                SELECT id FROM process_instances
                WHERE process_code = $1
                """,
                PROCESS_CODE,
            )
        ]
        instance_ids = list(dict.fromkeys([*from_bills, *extra]))
    for r in bill_rows:
        print(
            f"  命中账单 {r['id']} {r['check_date']} / {r['check_amount']} "
            f"{r['check_status']} instance={r['process_instance_id']}"
        )
    if instance_ids and not bill_rows:
        print(f"  另有 {len(instance_ids)} 个对账单流程实例（无账单行或账单已空）")
    return instance_ids


async def collect_standalone_stmt_task_ids(
    conn: asyncpg.Connection,
    *,
    full_clear: bool,
) -> list[str]:
    """填单页查询收货等未挂实例的对账单任务。仅全量模式清理。"""
    if not full_clear:
        return []
    rows = await conn.fetch(
        """
        SELECT id FROM automation_tasks
        WHERE task_type = ANY($1::text[])
          AND process_instance_id IS NULL
        """,
        STMT_TASK_TYPES,
    )
    return [r["id"] for r in rows]


async def delete_tasks_and_runs(conn: asyncpg.Connection, task_ids: list[str]) -> list[str]:
    logs: list[str] = []
    if not task_ids:
        logs.append("standalone_stmt_tasks: 0")
        return logs
    run_ids = [
        r["id"]
        for r in await conn.fetch(
            "SELECT id FROM rpa_runs WHERE task_id = ANY($1::text[])",
            task_ids,
        )
    ]
    logs.append(f"standalone_stmt_tasks: {len(task_ids)}")
    logs.append(f"standalone_stmt_runs: {len(run_ids)}")
    if run_ids:
        logs.append(await _delete_where_in(conn, "run_events", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "step_runs", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "worker_leases", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "human_actions", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "artifacts", "run_id", run_ids))
    logs.append(await _delete_where_in(conn, "task_messages", "task_id", task_ids))
    logs.append(await _delete_where_in(conn, "artifacts", "task_id", task_ids))
    logs.append(await _delete_where_in(conn, "human_actions", "task_id", task_ids))
    logs.append(await _delete_where_in(conn, "worker_leases", "task_id", task_ids))
    logs.append(await _delete_where_in(conn, "rpa_runs", "task_id", task_ids))
    logs.append(await _delete_where_in(conn, "automation_tasks", "id", task_ids))
    return logs


async def preview(
    conn: asyncpg.Connection,
    instance_ids: list[str],
    standalone_task_ids: list[str],
    bill_ids: list[str] | None,
) -> dict[str, int]:
    task_ids = await collect_linked_task_ids(conn, instance_ids)
    run_ids = (
        [
            r["id"]
            for r in await conn.fetch(
                "SELECT id FROM rpa_runs WHERE task_id = ANY($1::text[])",
                task_ids,
            )
        ]
        if task_ids
        else []
    )
    if bill_ids:
        bill_count = await conn.fetchval(
            "SELECT count(*) FROM statement_bills WHERE id = ANY($1::text[])",
            bill_ids,
        )
    elif await _table_exists(conn, "statement_bills"):
        bill_count = await conn.fetchval("SELECT count(*) FROM statement_bills")
    else:
        bill_count = 0
    return {
        "statement_bills": int(bill_count or 0),
        "statement_process_instances": len(instance_ids),
        "linked_automation_tasks": len(task_ids),
        "linked_rpa_runs": len(run_ids),
        "standalone_stmt_tasks": len(standalone_task_ids),
    }


async def hard_clear_statements(
    conn: asyncpg.Connection,
    instance_ids: list[str],
    standalone_task_ids: list[str],
    bill_ids: list[str] | None,
) -> list[str]:
    logs: list[str] = []
    if await _table_exists(conn, "statement_bills"):
        if bill_ids:
            logs.append(await _delete_where_in(conn, "statement_bills", "id", bill_ids))
        elif instance_ids:
            logs.append(
                await _delete_where_in(
                    conn, "statement_bills", "process_instance_id", instance_ids
                )
            )
            leftover = await conn.execute("DELETE FROM statement_bills")
            logs.append(f"statement_bills leftover: {leftover}")
        else:
            leftover = await conn.execute("DELETE FROM statement_bills")
            logs.append(f"statement_bills: {leftover}")
    else:
        logs.append("statement_bills: skip")

    if instance_ids:
        logs.extend(await hard_clear(conn, instance_ids))
    else:
        logs.append("process_instances: nothing matched")

    logs.extend(await delete_tasks_and_runs(conn, standalone_task_ids))
    return logs


async def main(yes: bool, bill_ids: list[str]) -> None:
    dsn = load_dsn()
    safe = dsn.split("@")[-1] if "@" in dsn else "(local)"
    print(f"目标库: {safe}")
    print(f"范围: process_code={PROCESS_CODE}（不影响客户订单）")
    if bill_ids:
        print(f"模式: 按对账单 id 删除 ({', '.join(bill_ids)})")
    else:
        print("模式: 全量清空对账单 SOP（含填单页未挂实例的查询任务）")

    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        instance_ids = await resolve_instance_ids(conn, bill_ids or None)
        standalone = await collect_standalone_stmt_task_ids(
            conn, full_clear=not bill_ids
        )
        if bill_ids and not instance_ids:
            print("没有可删除的对账单，退出。")
            raise SystemExit(1)

        counts = await preview(conn, instance_ids, standalone, bill_ids or None)
        print("当前计数:")
        for key, value in counts.items():
            print(f"  {key}: {value}")

        if not yes:
            print()
            print("这是预览模式，没有删除任何数据。")
            print("确认删除请执行:")
            if bill_ids:
                keys = " ".join(bill_ids)
                print(
                    rf"  .\.venv\Scripts\python.exe scripts\clear_statement_bills.py --yes {keys}"
                )
            else:
                print(
                    r"  .\.venv\Scripts\python.exe scripts\clear_statement_bills.py --yes"
                )
            return

        print()
        print("开始硬删…")
        async with conn.transaction():
            logs = await hard_clear_statements(
                conn, instance_ids, standalone, bill_ids or None
            )
        for line in logs:
            print(" ", line)

        if bill_ids:
            left = await conn.fetch(
                "SELECT id FROM statement_bills WHERE id = ANY($1::text[])",
                bill_ids,
            )
            print("删除后仍存在的指定账单:", [r["id"] for r in left] or "(无)")
        else:
            leftover_bills = (
                await conn.fetchval("SELECT count(*) FROM statement_bills")
                if await _table_exists(conn, "statement_bills")
                else 0
            )
            leftover_inst = await conn.fetchval(
                "SELECT count(*) FROM process_instances WHERE process_code = $1",
                PROCESS_CODE,
            )
            print("清空后计数:")
            print(f"  statement_bills: {leftover_bills}")
            print(f"  srm_tiandi_statement instances: {leftover_inst}")
        print("完成。")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="硬删对账单 SOP 及相关任务/Run（全量或按对账单 id）"
    )
    parser.add_argument(
        "bill_ids",
        nargs="*",
        metavar="BILL_ID",
        help="可选。传入一个或多个 statement_bills.id 则只删这些；不传则全量清空对账单 SOP",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="真正执行删除；不加则只打印计数预览",
    )
    args = parser.parse_args()
    try:
        asyncio.run(main(yes=args.yes, bill_ids=list(args.bill_ids)))
    except KeyboardInterrupt:
        sys.exit(130)
