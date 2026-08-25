# -*- coding: utf-8 -*-
"""联调用：硬删「流程实例」及相关任务/Run 数据，便于重新扫单。

================================================================================
用途
--------------------------------------------------------------------------------
客户订单 SOP 联调时，把库里已有的流程实例整树删掉，避免唯一约束
(portal + process_code + biz_key) 挡住重新扫单建单。

支持：
- 全量清空（不传单号）
- 按采购订单号只删指定实例（传一个或多个 PO）

================================================================================
会删什么（硬删，不可恢复）
--------------------------------------------------------------------------------
1) 范围内 process_line_items / process_stage_history / process_instances
2) 这些实例上 process_instance_id 非空的 automation_tasks，以及关联的：
   - task_successor_jobs（source_task_id / successor_task_id）
   - worker_leases / human_actions / task_messages / artifacts
   - run_events / step_runs / rpa_runs
3) 若有后继任务挂在上述任务链上，也会一并清理

不会动：
- workflow_templates / workflow_bindings
- portal_accounts
- rpa_engine Flow Registry（rpa_flow_*）
- MinIO 上的 Flow 包

================================================================================
怎么执行（在 service 目录）
--------------------------------------------------------------------------------
  cd d:\\work_space260811\\autotask-workspace\\service

  # 全量：只预览
  .\\.venv\\Scripts\\python.exe scripts\\clear_process_instances.py

  # 全量：确认删除
  .\\.venv\\Scripts\\python.exe scripts\\clear_process_instances.py --yes

  # 指定单号：预览
  .\\.venv\\Scripts\\python.exe scripts\\clear_process_instances.py POJS2607240005

  # 指定单号（可多个）：确认删除
  .\\.venv\\Scripts\\python.exe scripts\\clear_process_instances.py --yes POJS2607240005 POJS2607240006

依赖：
- service/.env 里的 DATABASE_URL（postgresql+asyncpg://...）
- 本机已装 asyncpg（service/.venv 里一般有）

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

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def load_dsn() -> str:
    env_path = SERVICE_ROOT / ".env"
    if not env_path.is_file():
        raise SystemExit(f"找不到 {env_path}，请确认在 service 工程下执行")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            return url.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit(f"{env_path} 中没有 DATABASE_URL")


async def _table_exists(conn: asyncpg.Connection, name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'public' AND table_name = $1
            )
            """,
            name,
        )
    )


async def _delete_where_in(
    conn: asyncpg.Connection,
    table: str,
    column: str,
    ids: list[str],
) -> str:
    if not ids or not await _table_exists(conn, table):
        return f"{table}: skip"
    result = await conn.execute(
        f"DELETE FROM {table} WHERE {column} = ANY($1::text[])",
        ids,
    )
    return f"{table}: {result}"


async def resolve_instance_ids(
    conn: asyncpg.Connection,
    biz_keys: list[str] | None,
) -> list[str] | None:
    """None = 全库；[] = 指定单号但没命中；非空 = 指定实例 id 列表。"""
    if not biz_keys:
        return None
    rows = await conn.fetch(
        """
        SELECT id, biz_key, stage, status
        FROM process_instances
        WHERE biz_key = ANY($1::text[])
        ORDER BY biz_key, created_at DESC
        """,
        biz_keys,
    )
    found = {r["biz_key"] for r in rows}
    missing = [k for k in biz_keys if k not in found]
    if missing:
        print(f"未找到实例: {', '.join(missing)}")
    for r in rows:
        print(f"  命中 {r['biz_key']} id={r['id']} {r['stage']}/{r['status']}")
    return [r["id"] for r in rows]


async def collect_linked_task_ids(
    conn: asyncpg.Connection,
    instance_ids: list[str] | None,
) -> list[str]:
    """收集挂在流程实例上的任务，以及它们的后继任务。

    instance_ids is None → 所有带 process_instance_id 的任务（全量）。
    """
    if instance_ids is None:
        root = [
            r["id"]
            for r in await conn.fetch(
                """
                SELECT id FROM automation_tasks
                WHERE process_instance_id IS NOT NULL
                """
            )
        ]
    else:
        if not instance_ids:
            return []
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


async def preview(
    conn: asyncpg.Connection,
    instance_ids: list[str] | None,
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

    if instance_ids is None:
        counts = {
            "process_instances": await conn.fetchval("SELECT count(*) FROM process_instances"),
            "process_line_items": await conn.fetchval("SELECT count(*) FROM process_line_items"),
            "process_stage_history": await conn.fetchval(
                "SELECT count(*) FROM process_stage_history"
            ),
            "linked_automation_tasks": len(task_ids),
            "linked_rpa_runs": len(run_ids),
        }
    else:
        counts = {
            "process_instances": len(instance_ids),
            "process_line_items": await conn.fetchval(
                "SELECT count(*) FROM process_line_items WHERE instance_id = ANY($1::text[])",
                instance_ids,
            )
            if instance_ids
            else 0,
            "process_stage_history": await conn.fetchval(
                "SELECT count(*) FROM process_stage_history WHERE instance_id = ANY($1::text[])",
                instance_ids,
            )
            if instance_ids
            else 0,
            "linked_automation_tasks": len(task_ids),
            "linked_rpa_runs": len(run_ids),
        }
    return counts


async def hard_clear(
    conn: asyncpg.Connection,
    instance_ids: list[str] | None,
) -> list[str]:
    logs: list[str] = []
    task_ids = await collect_linked_task_ids(conn, instance_ids)
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
                await _delete_where_in(
                    conn, "task_successor_jobs", "source_run_id", run_ids
                )
            )

    if task_ids:
        logs.append(await _delete_where_in(conn, "task_messages", "task_id", task_ids))
        logs.append(await _delete_where_in(conn, "artifacts", "task_id", task_ids))
        logs.append(await _delete_where_in(conn, "human_actions", "task_id", task_ids))
        logs.append(await _delete_where_in(conn, "worker_leases", "task_id", task_ids))
        if await _table_exists(conn, "task_successor_jobs"):
            logs.append(
                await _delete_where_in(
                    conn, "task_successor_jobs", "source_task_id", task_ids
                )
            )
            logs.append(
                await _delete_where_in(
                    conn, "task_successor_jobs", "successor_task_id", task_ids
                )
            )
        logs.append(await _delete_where_in(conn, "rpa_runs", "task_id", task_ids))
        logs.append(await _delete_where_in(conn, "automation_tasks", "id", task_ids))

    if instance_ids is None:
        for table in ("process_line_items", "process_stage_history", "process_instances"):
            if await _table_exists(conn, table):
                result = await conn.execute(f"DELETE FROM {table}")
                logs.append(f"{table}: {result}")
            else:
                logs.append(f"{table}: skip")
    else:
        if not instance_ids:
            logs.append("process_*: nothing matched")
            return logs
        logs.append(
            await _delete_where_in(conn, "process_line_items", "instance_id", instance_ids)
        )
        logs.append(
            await _delete_where_in(
                conn, "process_stage_history", "instance_id", instance_ids
            )
        )
        logs.append(await _delete_where_in(conn, "process_instances", "id", instance_ids))

    return logs


async def main(yes: bool, biz_keys: list[str]) -> None:
    dsn = load_dsn()
    safe = dsn.split("@")[-1] if "@" in dsn else "(local)"
    print(f"目标库: {safe}")
    if biz_keys:
        print(f"模式: 按单号删除 ({', '.join(biz_keys)})")
    else:
        print("模式: 全量清空流程实例")

    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        instance_ids = await resolve_instance_ids(conn, biz_keys or None)
        if biz_keys and instance_ids is not None and len(instance_ids) == 0:
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
            if biz_keys:
                keys = " ".join(biz_keys)
                print(
                    rf"  .\.venv\Scripts\python.exe scripts\clear_process_instances.py --yes {keys}"
                )
            else:
                print(
                    r"  .\.venv\Scripts\python.exe scripts\clear_process_instances.py --yes"
                )
            return

        print()
        print("开始硬删…")
        async with conn.transaction():
            logs = await hard_clear(conn, instance_ids)
        for line in logs:
            print(" ", line)

        after = await preview(conn, instance_ids if biz_keys else None)
        # 指定单号删除后，用空 instance 列表再数一次无意义；改查这些 biz_key 是否还在
        if biz_keys:
            left = await conn.fetch(
                "SELECT biz_key FROM process_instances WHERE biz_key = ANY($1::text[])",
                biz_keys,
            )
            print("删除后仍存在的同单号实例:", [r["biz_key"] for r in left] or "(无)")
        else:
            print("清空后计数:")
            for k, v in after.items():
                print(f"  {k}: {v}")
        print("完成。")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="硬删流程实例及相关任务/Run（全量或按采购订单号）"
    )
    parser.add_argument(
        "biz_keys",
        nargs="*",
        metavar="PO",
        help="可选。传入一个或多个采购订单号则只删这些；不传则全量清空",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="真正执行删除；不加则只打印计数预览",
    )
    args = parser.parse_args()
    try:
        asyncio.run(main(yes=args.yes, biz_keys=list(args.biz_keys)))
    except KeyboardInterrupt:
        sys.exit(130)
