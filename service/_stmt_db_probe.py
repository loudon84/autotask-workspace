"""Read-only: copy structure of an existing 天地伟业 template/binding for statement setup."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

PORTAL = "b182630d-5023-45c3-ac9c-6b022765b7e1"


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        templates = list(
            await conn.execute(
                text(
                    "select id, name, code, created_by, input_schema, business_steps "
                    "from workflow_templates "
                    "where tenant_id='2be7c618-326d-4a73-91ea-1cfda10f7073' "
                    "and deleted_at is null order by code"
                )
            )
        )
        print("templates")
        for row in templates:
            print(row[0], row[1], row[2], row[3])
            print("  input", (row[4] or "")[:300])
            print("  steps", (row[5] or "")[:300])
        binds = list(
            await conn.execute(
                text(
                    "select wb.id, wt.code, wb.rpa_flow_version_id, wb.flow_checksum_snapshot, wb.config, wb.created_by "
                    "from workflow_bindings wb "
                    "join workflow_templates wt on wt.id=wb.workflow_template_id "
                    "where wb.portal_account_id=:portal and wt.code='srm_scan_pending_orders'"
                ),
                {"portal": PORTAL},
            )
        )
        print("scan_binding")
        for row in binds:
            print("id", row[0])
            print("version_id", row[2])
            print("checksum", row[3])
            print("config", row[4])
            print("created_by", row[5])
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
