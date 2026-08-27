# -*- coding: utf-8 -*-
"""联调用：硬删全部任务/Run 运行时数据，不动 Binding / 门户 / 调度。

客户订单、对账单脚本只清挂了流程实例的任务。扫单、回签、未挂实例的建单
会留在任务列表。本脚本清整张 automation_tasks 及相关子表。
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
    hard_clear,
    load_dsn,
)
from clear_statement_bills import delete_tasks_and_runs  # noqa: E402


async def preview(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        """
        SELECT task_type, status, count(*) AS n
        FROM automation_tasks
        GROUP BY task_type, status
        ORDER BY n DESC
        """
    )
    print("任务按类型/状态:")
    total = 0
    for r in rows:
        print(f"  {r['task_type']:40} {r['status']:16} {r['n']}")
        total += int(r["n"])
    print(f"automation_tasks: {total}")
    print("rpa_runs:", await conn.fetchval("SELECT count(*) FROM rpa_runs"))
    if await _table_exists(conn, "integration_call_logs"):
        print(
            "integration_call_logs:",
            await conn.fetchval("SELECT count(*) FROM integration_call_logs"),
        )
    print(
        "process_instances:",
        await conn.fetchval("SELECT count(*) FROM process_instances"),
    )
    if await _table_exists(conn, "statement_bills"):
        print(
            "statement_bills:",
            await conn.fetchval("SELECT count(*) FROM statement_bills"),
        )


async def hard_clear_all_tasks(conn: asyncpg.Connection) -> list[str]:
    logs: list[str] = []
    task_ids = [r["id"] for r in await conn.fetch("SELECT id FROM automation_tasks")]
    logs.append(f"all_tasks: {len(task_ids)}")
    if await _table_exists(conn, "task_successor_jobs"):
        result = await conn.execute("DELETE FROM task_successor_jobs")
        logs.append(f"task_successor_jobs: {result}")
    if task_ids:
        logs.append(await _delete_where_in(conn, "run_events", "task_id", task_ids))
    logs.extend(await delete_tasks_and_runs(conn, task_ids))
    if await _table_exists(conn, "integration_call_logs"):
        result = await conn.execute("DELETE FROM integration_call_logs")
        logs.append(f"integration_call_logs: {result}")
    leftover_runs = await conn.fetchval("SELECT count(*) FROM rpa_runs")
    if leftover_runs:
        logs.append(f"leftover_rpa_runs_before_sweep: {leftover_runs}")
        run_ids = [r["id"] for r in await conn.fetch("SELECT id FROM rpa_runs")]
        logs.append(await _delete_where_in(conn, "run_events", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "step_runs", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "worker_leases", "run_id", run_ids))
        result = await conn.execute("DELETE FROM rpa_runs")
        logs.append(f"rpa_runs leftover: {result}")
    logs.extend(await hard_clear(conn, None))
    if await _table_exists(conn, "statement_bills"):
        result = await conn.execute("DELETE FROM statement_bills")
        logs.append(f"statement_bills: {result}")
    return logs


async def main(yes: bool) -> None:
    dsn = load_dsn()
    print(f"目标库: {dsn.split('@')[-1] if '@' in dsn else '(local)'}")
    print("模式: 清空全部任务/Run/流程实例/对账单（保留 Binding/门户/调度）")
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        await preview(conn)
        if not yes:
            print()
            print("这是预览模式，没有删除任何数据。")
            print(r"确认删除: uv run python scripts\clear_all_runtime_tasks.py --yes")
            return
        print()
        print("开始硬删…")
        async with conn.transaction():
            logs = await hard_clear_all_tasks(conn)
        for line in logs:
            print(" ", line)
        print("清空后:")
        await preview(conn)
        print("完成。")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="硬删全部任务运行时数据")
    parser.add_argument("--yes", action="store_true", help="真正执行删除")
    args = parser.parse_args()
    try:
        asyncio.run(main(yes=args.yes))
    except KeyboardInterrupt:
        sys.exit(130)
