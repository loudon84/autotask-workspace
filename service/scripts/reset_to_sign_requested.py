# -*- coding: utf-8 -*-
"""联调用：把指定采购订单号的流程实例刷回「待回签」，便于复测回签轮询。

================================================================================
用途
--------------------------------------------------------------------------------
已完成 / 已回签 / 失败等实例，改回 SIGN_REQUESTED + ACTIVE，并去掉会挡住
回签探测的归档任务（SUCCESS / 进行中的 srm_upload_order_attachment）。

================================================================================
怎么执行（在 service 目录）
--------------------------------------------------------------------------------
  cd d:\\work_space260811\\autotask-workspace\\service

  # 预览（不改库）
  .\\.venv\\Scripts\\python.exe scripts\\reset_to_sign_requested.py POJS2607240005

  # 真正执行（可多个单号）
  .\\.venv\\Scripts\\python.exe scripts\\reset_to_sign_requested.py --yes POJS2607240005 POJS2607240006

依赖：service/.env 的 DATABASE_URL；本机 asyncpg（.venv 一般有）。

================================================================================
会改什么
--------------------------------------------------------------------------------
1) process_instances：stage=SIGN_REQUESTED，status=ACTIVE，清空 last_error_*
2) 写一条 process_stage_history（actor=scripts/reset_to_sign_requested）
3) 软删会挡住 create_check_reply_task 的归档任务：
   task_type=srm_upload_order_attachment 且 status∈
   QUEUED/RUNNING/WAITING_HUMAN/SUCCESS/SUCCESS_MANUAL
4) 软删进行中的回签探测（QUEUED/RUNNING/WAITING_HUMAN），避免「已有探测在飞」跳过

不会：硬删实例、不会动交期行、不会删签章/建单等历史 SUCCESS 任务。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

SERVICE_ROOT = Path(__file__).resolve().parents[1]

ARCHIVE_TYPE = "srm_upload_order_attachment"
CHECK_REPLY_TYPE = "srm_check_reply_status"
ARCHIVE_BLOCK = ("QUEUED", "RUNNING", "WAITING_HUMAN", "SUCCESS", "SUCCESS_MANUAL")
CHECK_IN_FLIGHT = ("QUEUED", "RUNNING", "WAITING_HUMAN")
TARGET_STAGE = "SIGN_REQUESTED"
TARGET_STATUS = "ACTIVE"
ACTOR = "scripts/reset_to_sign_requested"


def load_dsn() -> str:
    env_path = SERVICE_ROOT / ".env"
    if not env_path.is_file():
        raise SystemExit(f"找不到 {env_path}，请确认在 service 工程下执行")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            return url.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit(f"{env_path} 中没有 DATABASE_URL")


async def find_instances(conn: asyncpg.Connection, biz_keys: list[str]) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT id, biz_key, stage, status, last_error_code,
               deleted_at IS NOT NULL AS soft_deleted
        FROM process_instances
        WHERE biz_key = ANY($1::text[])
        ORDER BY biz_key, created_at DESC
        """,
        biz_keys,
    )


async def preview_blockers(conn: asyncpg.Connection, instance_id: str) -> dict[str, int]:
    archive_n = await conn.fetchval(
        """
        SELECT count(*) FROM automation_tasks
        WHERE process_instance_id = $1
          AND task_type = $2
          AND deleted_at IS NULL
          AND status = ANY($3::text[])
        """,
        instance_id,
        ARCHIVE_TYPE,
        list(ARCHIVE_BLOCK),
    )
    check_n = await conn.fetchval(
        """
        SELECT count(*) FROM automation_tasks
        WHERE process_instance_id = $1
          AND task_type = $2
          AND deleted_at IS NULL
          AND status = ANY($3::text[])
        """,
        instance_id,
        CHECK_REPLY_TYPE,
        list(CHECK_IN_FLIGHT),
    )
    return {"archive_block": int(archive_n or 0), "check_in_flight": int(check_n or 0)}


async def reset_one(conn: asyncpg.Connection, row: asyncpg.Record, now: datetime) -> list[str]:
    logs: list[str] = []
    iid = row["id"]
    from_stage = row["stage"]

    await conn.execute(
        """
        UPDATE process_instances
        SET stage = $1,
            status = $2,
            last_error_code = NULL,
            last_error_message = NULL,
            deleted_at = NULL,
            updated_at = $3
        WHERE id = $4
        """,
        TARGET_STAGE,
        TARGET_STATUS,
        now,
        iid,
    )
    logs.append(f"instance {row['biz_key']}: {from_stage}/{row['status']} -> {TARGET_STAGE}/{TARGET_STATUS}")

    await conn.execute(
        """
        INSERT INTO process_stage_history
          (id, instance_id, from_stage, to_stage, actor, note, created_at, updated_at, deleted_at)
        VALUES
          ($1, $2, $3, $4, $5, $6, $7, $7, NULL)
        """,
        str(uuid.uuid4()),
        iid,
        from_stage,
        TARGET_STAGE,
        ACTOR,
        "联调脚本刷回待回签，便于复测回签轮询",
        now,
    )
    logs.append("  + stage_history")

    archived = await conn.fetch(
        """
        SELECT id, status, title FROM automation_tasks
        WHERE process_instance_id = $1
          AND task_type = $2
          AND deleted_at IS NULL
          AND status = ANY($3::text[])
        """,
        iid,
        ARCHIVE_TYPE,
        list(ARCHIVE_BLOCK),
    )
    for t in archived:
        await conn.execute(
            "UPDATE automation_tasks SET deleted_at = $1, updated_at = $1 WHERE id = $2",
            now,
            t["id"],
        )
        logs.append(f"  soft-delete archive {t['id'][:8]}… {t['status']}")

    inflight = await conn.fetch(
        """
        SELECT id, status, title FROM automation_tasks
        WHERE process_instance_id = $1
          AND task_type = $2
          AND deleted_at IS NULL
          AND status = ANY($3::text[])
        """,
        iid,
        CHECK_REPLY_TYPE,
        list(CHECK_IN_FLIGHT),
    )
    for t in inflight:
        await conn.execute(
            "UPDATE automation_tasks SET deleted_at = $1, updated_at = $1 WHERE id = $2",
            now,
            t["id"],
        )
        logs.append(f"  soft-delete check_reply inflight {t['id'][:8]}… {t['status']}")

    return logs


async def main(biz_keys: list[str], yes: bool) -> None:
    if not biz_keys:
        raise SystemExit("请至少传一个采购订单号，例如: POJS2607240005")

    dsn = load_dsn()
    safe = dsn.split("@")[-1] if "@" in dsn else "(local)"
    print(f"目标库: {safe}")
    print(f"单号: {', '.join(biz_keys)}")

    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        rows = await find_instances(conn, biz_keys)
        found = {r["biz_key"] for r in rows}
        missing = [k for k in biz_keys if k not in found]
        if missing:
            print(f"未找到实例: {', '.join(missing)}")
        if not rows:
            raise SystemExit(1)

        # 同单多实例时全部处理（按 created_at desc 列出）
        print("将处理:")
        for r in rows:
            blockers = await preview_blockers(conn, r["id"])
            flag = " [已软删]" if r["soft_deleted"] else ""
            print(
                f"  {r['biz_key']} id={r['id'][:8]}… "
                f"{r['stage']}/{r['status']}{flag} "
                f"archive_block={blockers['archive_block']} "
                f"check_in_flight={blockers['check_in_flight']}"
            )

        if not yes:
            print()
            print("预览模式，未改库。确认执行请加 --yes，例如:")
            print(
                r"  .\.venv\Scripts\python.exe scripts\reset_to_sign_requested.py "
                f"--yes {' '.join(biz_keys)}"
            )
            return

        now = datetime.now(timezone.utc)
        print()
        print("开始刷回待回签…")
        async with conn.transaction():
            for r in rows:
                for line in await reset_one(conn, r, now):
                    print(" ", line)
        print("完成。可点「立即回签轮询」复测。")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="把指定 PO 的流程实例刷回待回签（SIGN_REQUESTED）"
    )
    parser.add_argument(
        "biz_keys",
        nargs="+",
        metavar="PO",
        help="采购订单号，可多个",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="真正写库；不加则只预览",
    )
    args = parser.parse_args()
    try:
        asyncio.run(main(biz_keys=args.biz_keys, yes=args.yes))
    except KeyboardInterrupt:
        sys.exit(130)
