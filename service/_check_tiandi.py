"""Print all 天地伟业 portals and their bindings."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.deps import async_session_factory
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate


async def main() -> None:
    async with async_session_factory() as db:
        portals = (
            await db.execute(
                select(
                    PortalAccount.id,
                    PortalAccount.portal_name,
                    PortalAccount.portal_url,
                    PortalAccount.login_account,
                    PortalAccount.entity_type,
                    PortalAccount.erp_entity_code,
                    PortalAccount.erp_entity_name,
                    PortalAccount.business_entity,
                    PortalAccount.ou,
                    PortalAccount.status,
                )
                .where(not_deleted(PortalAccount))
                .order_by(PortalAccount.portal_name)
            )
        ).all()
        print("=== Portals ===")
        for p in portals:
            print(
                f"{p.portal_name} | id={p.id[:8]} | url={p.portal_url} | "
                f"login={p.login_account} | type={p.entity_type} | "
                f"code={p.erp_entity_code} | name={p.erp_entity_name} | "
                f"biz={p.business_entity} | ou={p.ou} | {p.status}"
            )

        print("\n=== Bindings ===")
        rows = (
            await db.execute(
                select(
                    WorkflowBinding.id.label("bid"),
                    WorkflowBinding.portal_account_id,
                    PortalAccount.portal_name,
                    WorkflowTemplate.code.label("template_code"),
                    WorkflowTemplate.name.label("template_name"),
                    WorkflowBinding.rpa_flow_id,
                    WorkflowBinding.rpa_flow_version,
                    WorkflowBinding.status,
                )
                .join(WorkflowTemplate, WorkflowTemplate.id == WorkflowBinding.workflow_template_id)
                .outerjoin(PortalAccount, PortalAccount.id == WorkflowBinding.portal_account_id)
                .where(not_deleted(WorkflowBinding), not_deleted(WorkflowTemplate))
                .order_by(WorkflowTemplate.code, PortalAccount.portal_name)
            )
        ).all()
        for r in rows:
            print(
                f"{r.template_code} | {r.template_name} | "
                f"portal={r.portal_name}({r.portal_account_id[:8]}) | "
                f"flow={r.rpa_flow_id}@{r.rpa_flow_version} | {r.status}"
            )


if __name__ == "__main__":
    asyncio.run(main())
