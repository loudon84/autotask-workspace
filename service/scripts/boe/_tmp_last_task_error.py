"""临时：查最新 enrich 任务的 Run 事件日志（定位真实报错）。"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402


async def main() -> None:
    eng = create_async_engine(os.environ["DATABASE_URL"])
    async with eng.connect() as c:
        art = (
            await c.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND (table_name LIKE '%artifact%' "
                    "OR table_name LIKE '%file%' OR table_name LIKE '%object%')"
                )
            )
        ).fetchall()
        print("artifact tables:", [r[0] for r in art])
        for t in [r[0] for r in art]:
            cols = (
                await c.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name=:t ORDER BY ordinal_position"
                    ),
                    {"t": t},
                )
            ).fetchall()
            colnames = [r[0] for r in cols]
            print(t, "cols:", colnames)
            rows = (
                await c.execute(text(f"SELECT * FROM {t} ORDER BY 1 DESC LIMIT 3"))
            ).fetchall()
            for r in rows:
                print("  ", str(r)[:400])
        tables = (
            await c.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )
            )
        ).fetchall()
        names = [r[0] for r in tables]
        print("run/event tables:", [n for n in names if "run" in n or "event" in n or "log" in n])

        task_id = "55e14502-727e-458b-873b-83e88632eae5"
        for t in [n for n in names if "run" in n]:
            cols = (
                await c.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name=:t ORDER BY ordinal_position"
                    ),
                    {"t": t},
                )
            ).fetchall()
            colnames = [r[0] for r in cols]
            link = next((n for n in colnames if "task" in n and "id" in n), None)
            if not link:
                continue
            keep = [n for n in colnames if n in ("id", "status", "level", "message", "error_code", "error_message", "created_at", "event_type", "run_id", "seq")]
            if not keep:
                continue
            order = "created_at" if "created_at" in colnames else colnames[0]
            rows = (
                await c.execute(
                    text(f"SELECT {', '.join(keep)} FROM {t} WHERE {link}=:tid ORDER BY {order} DESC LIMIT 25"),
                    {"tid": task_id},
                )
            ).fetchall()
            print(f"\n== {t} ({len(rows)} rows) ==")
            for r in reversed(rows):
                line = " | ".join(f"{k}={str(v)[:220]}" for k, v in zip(keep, r) if v is not None)
                print(" ", line)
    await eng.dispose()


asyncio.run(main())
