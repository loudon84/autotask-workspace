"""临时：查当前箱单实例行数据(regionCode/regionSrmName) + 地区映射表行数。"""
import asyncio
import json
import os

from dotenv import load_dotenv

load_dotenv()
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402


async def main() -> None:
    eng = create_async_engine(os.environ["DATABASE_URL"])
    async with eng.connect() as c:
        row = (
            await c.execute(
                text(
                    "SELECT id, biz_key, stage, status, summary FROM process_instances "
                    "WHERE process_code='srm_boe_invoice_packing' AND deleted_at IS NULL "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            )
        ).fetchone()
        print("instance:", row[0], row[1], row[2], row[3])
        summary = row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}")
        for ln in summary.get("lines") or []:
            print(
                "  line:",
                json.dumps(
                    {k: ln.get(k) for k in ("poNum", "itemNum", "regionCode", "regionSrmName", "deliveryQty", "netWeight")},
                    ensure_ascii=False,
                ),
            )
        cnt = (
            await c.execute(text("SELECT count(*), count(boe_name) FROM region_code_maps"))
        ).fetchone()
        print("region_code_maps: total =", cnt[0], ", 有 boe_name =", cnt[1])
        rows = (
            await c.execute(
                text("SELECT region_code, default_name, boe_name FROM region_code_maps LIMIT 10")
            )
        ).fetchall()
        for r in rows:
            print("  map:", r[0], "|", r[1], "|", r[2])
    await eng.dispose()


asyncio.run(main())
