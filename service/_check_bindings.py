"""Print current WorkflowBinding versions for supplier portal flows."""

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
        rows = (
            await db.execute(
                select(
                    WorkflowBinding.id,
                    WorkflowBinding.portal_account_id,
                    WorkflowBinding.rpa_flow_id,
                    WorkflowBinding.rpa_flow_version,
                    WorkflowBinding.rpa_flow_version_id,
                    WorkflowBinding.status,
                    WorkflowTemplate.code.label("template_code"),
                    WorkflowTemplate.name.label("template_name"),
                    PortalAccount.portal_name,
                    PortalAccount.erp_entity_code,
                    PortalAccount.business_entity,
                    PortalAccount.ou,
                )
                .join(
                    WorkflowTemplate,
                    WorkflowTemplate.id == WorkflowBinding.workflow_template_id,
                )
                .outerjoin(
                    PortalAccount,
                    PortalAccount.id == WorkflowBinding.portal_account_id,
                )
                .where(
                    not_deleted(WorkflowBinding),
                    not_deleted(WorkflowTemplate),
                    WorkflowTemplate.code.in_([
                        "srm_prepare_erp_order",
                        "srm_upload_order_attachment",
                    ]),
                )
                .order_by(WorkflowTemplate.code, PortalAccount.portal_name)
            )
        ).all()
        for r in rows:
            print(
                r.template_code,
                "| binding", r.id[:8],
                "| portal", (r.portal_name or "?"),
                "| flow", r.rpa_flow_version,
                "| status", r.status,
                "| entityCode", repr(r.erp_entity_code),
                "| businessEntity", repr(r.business_entity),
                "| ou", repr(r.ou),
            )


if __name__ == "__main__":
    asyncio.run(main())
