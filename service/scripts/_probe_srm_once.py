"""One-off: probe SRM upload dialog DOM. Do not commit."""
import asyncio
import json
from pathlib import Path

url = None
env_path = Path(__file__).resolve().parents[1] / ".env.product"
for line in env_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        url = line.split("=", 1)[1].strip()
url = url.replace("postgresql+asyncpg://", "postgresql://")

import asyncpg

PORTAL_ID = "9c13041f-da3d-497b-83c8-bd952abfbea4"


async def main():
    conn = await asyncpg.connect(url)
    try:
        row = await conn.fetchrow(
            "SELECT portal_name, portal_url, account, password FROM portal_accounts WHERE id = $1",
            PORTAL_ID,
        )
        print(json.dumps({k: row[k] for k in row.keys()}, ensure_ascii=False))
    finally:
        await conn.close()


asyncio.run(main())
