"""临时：查引擎侧最近 Run 的错误与日志事件。"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402


async def main() -> None:
    eng = create_async_engine(os.environ["DATABASE_URL"])
    schema = os.environ.get("DATABASE_SCHEMA", "rpa_engine")
    async with eng.connect() as c:
        tables = (
            await c.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema=:s ORDER BY table_name"
                ),
                {"s": schema},
            )
        ).fetchall()
        names = [r[0] for r in tables]
        print("tables:", [n for n in names if "run" in n or "log" in n or "event" in n])
        run_table = next((n for n in names if n.endswith("runs") or n == "runs"), None)
        if run_table:
            cols = (
                await c.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema=:s AND table_name=:t ORDER BY ordinal_position"
                    ),
                    {"s": schema, "t": run_table},
                )
            ).fetchall()
            colnames = [r[0] for r in cols]
            keep = [
                n
                for n in colnames
                if n
                in (
                    "id",
                    "status",
                    "error_code",
                    "error_message",
                    "finished_at",
                    "updated_at",
                    "created_at",
                    "flow_id",
                    "rpa_flow_id",
                )
            ]
            rows = (
                await c.execute(
                    text(
                        f"SELECT {', '.join(keep)} FROM {schema}.{run_table} "
                        "ORDER BY created_at DESC LIMIT 3"
                    )
                )
            ).fetchall()
            for r in rows:
                print("---")
                for k, v in zip(keep, r):
                    print(f"  {k}: {str(v)[:400]}")
    await eng.dispose()


asyncio.run(main())
