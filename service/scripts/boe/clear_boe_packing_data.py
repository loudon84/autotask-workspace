# -*- coding: utf-8 -*-
"""联调用：硬删京东方发票箱单（srm_boe_invoice_packing）测试数据，便于反复匹配测试。

================================================================================
用途
--------------------------------------------------------------------------------
京东方发票箱单 SOP 联调时，把库里的箱单流程实例整树删掉，避免「交货计划已匹配」
挡住所重新匹配建单。与天地伟业脚本（scripts/clear_process_instances.py 等）分开，
只动京东方箱单，绝不清客户订单/对账单数据。

支持：
- 清空全部京东方箱单实例（不传参数）
- 按交货计划单号只删指定实例（传一个或多个 doc_no）

================================================================================
会删什么（硬删，不可恢复）
--------------------------------------------------------------------------------
1) 范围内 process_line_items / process_stage_history / process_instances
   （仅 process_code = 'srm_boe_invoice_packing'）
2) 这些实例上 process_instance_id 非空的 automation_tasks，以及关联的：
   - task_successor_jobs（source_task_id / successor_task_id）
   - worker_leases / human_actions / task_messages / artifacts
   - run_events / step_runs / rpa_runs

不会动：
- workflow_templates / workflow_bindings / portal_accounts / region_code_maps
- 天地伟业等其他流程的实例与任务
- timer 配置（调度中心里「京东方-匹配交货计划」开关保持原样）

================================================================================
怎么执行（在 service 目录）
--------------------------------------------------------------------------------
  cd d:\\work_space260811\\autotask-workspace\\service

  # 全部京东方箱单：只预览
  uv run python scripts\\boe\\clear_boe_packing_data.py

  # 全部京东方箱单：确认删除
  uv run python scripts\\boe\\clear_boe_packing_data.py --yes

  # 指定交货计划单号：预览 / 确认删除
  uv run python scripts\\boe\\clear_boe_packing_data.py 101SJH2026040195
  uv run python scripts\\boe\\clear_boe_packing_data.py --yes 101SJH2026040195

依赖：service/.env 里的 DATABASE_URL；service/.venv 里的 asyncpg。

================================================================================
注意
--------------------------------------------------------------------------------
- 这是联调重置脚本，不是产品能力；生产环境不要跑。
- 跑之前建议停一下正在执行的相关任务，或接受 Run 可能报错。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from clear_process_instances import (  # noqa: E402
    _delete_where_in,
    _table_exists,
    load_dsn,
)

BOE_PROCESS_CODE = "srm_boe_invoice_packing"


async def resolve_instance_ids(
    conn: asyncpg.Connection,
    doc_nos: list[str] | None,
) -> list[str] | None:
    """None = 全部京东方箱单；[] = 指定单号没命中；非空 = 指定实例 id 列表。"""
    if doc_nos:
        rows = await conn.fetch(
            """
            SELECT id, biz_key, stage, status
            FROM process_instances
            WHERE process_code = $1 AND biz_key = ANY($2::text[])
            ORDER BY biz_key, created_at DESC
            """,
            BOE_PROCESS_CODE,
            doc_nos,
        )
        found = {r["biz_key"] for r in rows}
        missing = [k for k in doc_nos if k not in found]
        if missing:
            print(f"未找到京东方箱单实例: {', '.join(missing)}")
        for r in rows:
            print(f"  命中 {r['biz_key']} id={r['id']} {r['stage']}/{r['status']}")
        return [r["id"] for r in rows]
    rows = await conn.fetch(
        """
        SELECT id, biz_key, stage, status
        FROM process_instances
        WHERE process_code = $1
        ORDER BY created_at DESC
        """,
        BOE_PROCESS_CODE,
    )
    for r in rows:
        print(f"  命中 {r['biz_key']} id={r['id']} {r['stage']}/{r['status']}")
    return [r["id"] for r in rows] if rows else None


async def collect_linked_task_ids(
    conn: asyncpg.Connection,
    instance_ids: list[str] | None,
) -> list[str]:
    """挂在京东方箱单实例上的任务及其后继任务。None → 所有京东方箱单实例的任务。"""
    if instance_ids is not None and not instance_ids:
        return []
    if instance_ids is None:
        root = [
            r["id"]
            for r in await conn.fetch(
                """
                SELECT t.id FROM automation_tasks t
                JOIN process_instances p ON p.id = t.process_instance_id
                WHERE p.process_code = $1
                """,
                BOE_PROCESS_CODE,
            )
        ]
    else:
        root = [
            r["id"]
            for r in await conn.fetch(
                """
                SELECT id FROM automation_tasks
                WHERE process_instance_id = ANY($1::text[])
                """,
                instance_ids,
            )
        ]
    if not root:
        return []
    task_ids = set(root)
    if await _table_exists(conn, "task_successor_jobs"):
        rows = await conn.fetch(
            """
            SELECT successor_task_id
            FROM task_successor_jobs
            WHERE source_task_id = ANY($1::text[])
              AND successor_task_id IS NOT NULL
            """,
            list(task_ids),
        )
        for r in rows:
            task_ids.add(r["successor_task_id"])
    return list(task_ids)


async def preview(conn: asyncpg.Connection, instance_ids: list[str] | None) -> dict[str, int]:
    task_ids = await collect_linked_task_ids(conn, instance_ids)
    if instance_ids is None:
        instance_count = await conn.fetchval(
            "SELECT count(*) FROM process_instances WHERE process_code = $1",
            BOE_PROCESS_CODE,
        )
        line_count = await conn.fetchval(
            """
            SELECT count(*) FROM process_line_items li
            JOIN process_instances p ON p.id = li.instance_id
            WHERE p.process_code = $1
            """,
            BOE_PROCESS_CODE,
        )
        history_count = await conn.fetchval(
            """
            SELECT count(*) FROM process_stage_history h
            JOIN process_instances p ON p.id = h.instance_id
            WHERE p.process_code = $1
            """,
            BOE_PROCESS_CODE,
        )
    else:
        instance_count = len(instance_ids)
        line_count = (
            await conn.fetchval(
                "SELECT count(*) FROM process_line_items WHERE instance_id = ANY($1::text[])",
                instance_ids,
            )
            if instance_ids
            else 0
        )
        history_count = (
            await conn.fetchval(
                "SELECT count(*) FROM process_stage_history WHERE instance_id = ANY($1::text[])",
                instance_ids,
            )
            if instance_ids
            else 0
        )
    run_count = 0
    if task_ids:
        run_count = await conn.fetchval(
            "SELECT count(*) FROM rpa_runs WHERE task_id = ANY($1::text[])",
            task_ids,
        )
    return {
        "process_instances": instance_count,
        "process_line_items": line_count,
        "process_stage_history": history_count,
        "linked_automation_tasks": len(task_ids),
        "linked_rpa_runs": run_count,
    }


async def hard_clear(conn: asyncpg.Connection, instance_ids: list[str] | None) -> list[str]:
    logs: list[str] = []
    if instance_ids is not None and not instance_ids:
        return ["nothing matched"]

    # 先把本次范围的实例 id 固定下来（None 时查全量京东方箱单）
    if instance_ids is None:
        scope_ids = [
            r["id"]
            for r in await conn.fetch(
                "SELECT id FROM process_instances WHERE process_code = $1",
                BOE_PROCESS_CODE,
            )
        ]
    else:
        scope_ids = instance_ids

    task_ids = await collect_linked_task_ids(conn, scope_ids)
    logs.append(f"linked_tasks: {len(task_ids)}")

    run_ids: list[str] = []
    if task_ids:
        run_ids = [
            r["id"]
            for r in await conn.fetch(
                "SELECT id FROM rpa_runs WHERE task_id = ANY($1::text[])",
                task_ids,
            )
        ]
    logs.append(f"linked_runs: {len(run_ids)}")

    if run_ids:
        logs.append(await _delete_where_in(conn, "run_events", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "step_runs", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "worker_leases", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "human_actions", "run_id", run_ids))
        logs.append(await _delete_where_in(conn, "artifacts", "run_id", run_ids))
        if await _table_exists(conn, "task_successor_jobs"):
            logs.append(
                await _delete_where_in(conn, "task_successor_jobs", "source_run_id", run_ids)
            )

    if task_ids:
        logs.append(await _delete_where_in(conn, "task_messages", "task_id", task_ids))
        logs.append(await _delete_where_in(conn, "artifacts", "task_id", task_ids))
        logs.append(await _delete_where_in(conn, "human_actions", "task_id", task_ids))
        logs.append(await _delete_where_in(conn, "worker_leases", "task_id", task_ids))
        if await _table_exists(conn, "task_successor_jobs"):
            logs.append(
                await _delete_where_in(conn, "task_successor_jobs", "source_task_id", task_ids)
            )
            logs.append(
                await _delete_where_in(conn, "task_successor_jobs", "successor_task_id", task_ids)
            )
        logs.append(await _delete_where_in(conn, "rpa_runs", "task_id", task_ids))
        logs.append(await _delete_where_in(conn, "automation_tasks", "id", task_ids))

    if scope_ids:
        logs.append(await _delete_where_in(conn, "process_line_items", "instance_id", scope_ids))
        logs.append(
            await _delete_where_in(conn, "process_stage_history", "instance_id", scope_ids)
        )
        logs.append(await _delete_where_in(conn, "process_instances", "id", scope_ids))
    else:
        logs.append("process_*: nothing to delete")
    return logs


async def main(yes: bool, doc_nos: list[str]) -> None:
    dsn = load_dsn()
    safe = dsn.split("@")[-1] if "@" in dsn else "(local)"
    print(f"目标库: {safe}")
    if doc_nos:
        print(f"模式: 按交货计划单号删除 ({', '.join(doc_nos)})")
    else:
        print("模式: 清空全部京东方箱单实例（仅 srm_boe_invoice_packing）")

    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        instance_ids = await resolve_instance_ids(conn, doc_nos or None)
        if doc_nos and not instance_ids:
            print("没有可删除的实例，退出。")
            raise SystemExit(1)

        counts = await preview(conn, instance_ids)
        print("当前计数:")
        for k, v in counts.items():
            print(f"  {k}: {v}")

        if not yes:
            print()
            print("这是预览模式，没有删除任何数据。")
            print("确认删除请执行:")
            keys = " ".join(doc_nos)
            suffix = f" {keys}" if keys else ""
            print(rf"  uv run python scripts\boe\clear_boe_packing_data.py --yes{suffix}")
            return

        print()
        print("开始硬删…")
        async with conn.transaction():
            logs = await hard_clear(conn, instance_ids)
        for line in logs:
            print(" ", line)

        left = await conn.fetchval(
            "SELECT count(*) FROM process_instances WHERE process_code = $1",
            BOE_PROCESS_CODE,
        )
        print(f"清空后京东方箱单实例剩余: {left}")
        print("完成。")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="硬删京东方发票箱单流程实例及相关任务/Run（全量或按交货计划单号）"
    )
    parser.add_argument(
        "doc_nos",
        nargs="*",
        metavar="DOC_NO",
        help="可选。传入一个或多个交货计划单号则只删这些；不传则清空全部京东方箱单实例",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="真正执行删除；不加则只打印计数预览",
    )
    args = parser.parse_args()
    try:
        asyncio.run(main(yes=args.yes, doc_nos=list(args.doc_nos)))
    except KeyboardInterrupt:
        sys.exit(130)
