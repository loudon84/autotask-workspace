"""Read run events for the failed statement query. No secrets."""

import asyncio
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

RUN_ID = "be06133a-7be2-48d6-96a6-18f3738d5bc9"


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        rows = list(
            await conn.execute(
                text(
                    "select type, level, message, payload "
                    "from run_events where run_id=:run_id order by created_at"
                ),
                {"run_id": RUN_ID},
            )
        )
        for row in rows:
            payload = row[3]
            print(row[0], row[1], row[2], str(payload)[:400])
        run = list(
            await conn.execute(
                text(
                    "select status, error_code, error_message, output "
                    "from rpa_runs where id=:run_id"
                ),
                {"run_id": RUN_ID},
            )
        )
        print("run", run)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
