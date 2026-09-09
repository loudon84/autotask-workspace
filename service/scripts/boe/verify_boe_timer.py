"""一次性验证：boe.pack_match 定时器是否登记、入口能否真实执行。

用法：uv run python scripts/boe/verify_boe_timer.py
只读 timers 表 + 调用一次真实入口（等价于调度中心点「立即执行」的通知环节）。
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(message)s")

from app.core.deps import async_session_factory  # noqa: E402
from app.services import timer_registry  # noqa: E402
from app.services import timer_service as timer_svc  # noqa: E402
from app.services.boe_timers import BOE_PACK_MATCH_TARGET, pack_match_due  # noqa: E402


async def main() -> None:
    async with async_session_factory() as db:
        row = await timer_svc.get_timer_by_target(db, BOE_PACK_MATCH_TARGET)
    if row is None:
        print(f"[FAIL] timers 表没有 target={BOE_PACK_MATCH_TARGET} 的行（启动登记未生效）")
        return
    print(
        f"[OK] 定时器已登记: id={row.id} name={row.name} "
        f"cron={row.cron} enabled={row.enabled}"
    )

    timer_registry.register(BOE_PACK_MATCH_TARGET, pack_match_due)
    had_listener, summary = await timer_registry.notify(BOE_PACK_MATCH_TARGET)
    print(
        f"[OK] notify 完成 had_listener={had_listener} "
        f"summary={summary or '-'}（入口已真实跑完一轮）"
    )


asyncio.run(main())
