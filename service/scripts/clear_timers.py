# -*- coding: utf-8 -*-
r"""联调用：硬删调度中心 timers / timer_runs，验证启动登记（ensure_catalog_rows）。

================================================================================
用途
--------------------------------------------------------------------------------
调度中心改 APScheduler 后，需要验证「启动登记」环节：清空 timers 表再重启
Task 4520，确认 lifespan 里的 ensure_catalog_rows 能把 5 条目录行
（demo.print_now / tiandy.scan_pending / tiandy.sign_poll / boe.pack_match /
boe.srm_login）按代码默认 cron、enabled=false 重新登记回来。

================================================================================
会删什么（硬删，不可恢复）
--------------------------------------------------------------------------------
1) timer_runs 全部执行记录
2) timers 全部定时器档案（含手工改过的 cron / 开关，重登记后回到代码默认值）

不会动：其它任何表。APScheduler 任务在进程内存里，不落库，无需清理。

================================================================================
怎么执行（在 service 目录）
--------------------------------------------------------------------------------
  cd d:\work_space260811\autotask-workspace\service

  # 只预览
  .\.venv\Scripts\python.exe scripts\clear_timers.py

  # 确认删除
  .\.venv\Scripts\python.exe scripts\clear_timers.py --yes

删完后重启：
  .\scripts\restart_task_4520.ps1

验收：调度中心重新出现 5 条目录行（enabled=false、默认 cron），
再次重启不会覆盖手工改过的 cron / 开关。

================================================================================
注意
--------------------------------------------------------------------------------
- 这是联调重置脚本，不是产品能力；生产环境不要跑。
- 运行中的服务 30 秒同步内会发现启用行消失并摘掉对应 APScheduler job，
  但目录行只有重启（lifespan）才会重新登记。
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

from clear_process_instances import _table_exists, load_dsn  # noqa: E402


async def preview(conn: asyncpg.Connection) -> None:
    if not await _table_exists(conn, "timers"):
        print("timers 表不存在（迁库待授权）")
        return
    rows = await conn.fetch(
        """
        SELECT target, name, cron, enabled
        FROM timers
        WHERE deleted_at IS NULL
        ORDER BY target
        """
    )
    print(f"timers: {len(rows)}")
    for r in rows:
        print(
            f"  {r['target']:24} enabled={str(r['enabled']):5} "
            f"cron={r['cron']:16} {r['name']}"
        )
    if await _table_exists(conn, "timer_runs"):
        print("timer_runs:", await conn.fetchval("SELECT count(*) FROM timer_runs"))


async def main(yes: bool) -> None:
    dsn = load_dsn()
    print(f"目标库: {dsn.split('@')[-1] if '@' in dsn else '(local)'}")
    print("模式: 清空调度中心（timers + timer_runs），验证启动登记")
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        await preview(conn)
        if not yes:
            print()
            print("这是预览模式，没有删除任何数据。")
            print(r"确认删除: .\.venv\Scripts\python.exe scripts\clear_timers.py --yes")
            return
        print()
        print("开始硬删…")
        async with conn.transaction():
            if await _table_exists(conn, "timer_runs"):
                print("  timer_runs:", await conn.execute("DELETE FROM timer_runs"))
            print("  timers:", await conn.execute("DELETE FROM timers"))
        print()
        print("完成。重启 Task 4520（.\\scripts\\restart_task_4520.ps1）后，")
        print("调度中心应重新登记 5 条目录行（enabled=false、代码默认 cron）。")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="硬删调度中心 timers / timer_runs")
    parser.add_argument("--yes", action="store_true", help="真正执行删除")
    args = parser.parse_args()
    try:
        asyncio.run(main(yes=args.yes))
    except KeyboardInterrupt:
        sys.exit(130)
