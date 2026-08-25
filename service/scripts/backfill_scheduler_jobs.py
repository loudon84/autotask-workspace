# -*- coding: utf-8 -*-
"""为现网扫单/回签 Binding 回填 config.schedule，并插入 scheduler_jobs。

默认 dry-run。需先授权 alembic upgrade 建表，再加 --apply 才写库。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.enums import BindingStatus
from app.models.portal_account import PortalAccount
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json, loads_json
from app.services.process_instance_service import (
    CHECK_REPLY_TEMPLATE_CODE,
    SCAN_TASK_TYPE,
)
from app.services.scheduler_job_service import sync_scheduler_job_from_binding

SCAN_SCHEDULE = {
    "enabled": True,
    "cron": "0 8 * * *",
    "processName": "客户订单",
    "actionName": "扫单",
}
SIGN_POLL_SCHEDULE = {
    "enabled": True,
    "cron": "*/30 * * * *",
    "processName": "客户订单",
    "actionName": "回签轮询",
}


def _default_schedule(template_code: str) -> dict | None:
    if template_code == SCAN_TASK_TYPE:
        return dict(SCAN_SCHEDULE)
    if template_code == CHECK_REPLY_TEMPLATE_CODE:
        return dict(SIGN_POLL_SCHEDULE)
    return None


async def main(apply: bool) -> int:
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(WorkflowBinding, WorkflowTemplate, PortalAccount)
                .join(
                    WorkflowTemplate,
                    WorkflowTemplate.id == WorkflowBinding.workflow_template_id,
                )
                .join(
                    PortalAccount,
                    PortalAccount.id == WorkflowBinding.portal_account_id,
                )
                .where(
                    WorkflowBinding.status == BindingStatus.ENABLED,
                    WorkflowTemplate.code.in_(
                        (SCAN_TASK_TYPE, CHECK_REPLY_TEMPLATE_CODE)
                    ),
                    not_deleted(WorkflowBinding),
                    not_deleted(WorkflowTemplate),
                    not_deleted(PortalAccount),
                )
            )
        ).all()
        planned = 0
        for binding, template, portal in rows:
            config = loads_json(binding.config, {})
            if not isinstance(config, dict):
                config = {}
            if "schedule" in config:
                continue
            schedule = _default_schedule(template.code)
            if schedule is None:
                continue
            planned += 1
            print(
                f"{'[APPLY]' if apply else '[DRY-RUN]'} "
                f"binding={binding.id} portal={portal.portal_name} "
                f"template={template.code} schedule={schedule}"
            )
            if not apply:
                continue
            config["schedule"] = schedule
            binding.config = dumps_json(config)
            await sync_scheduler_job_from_binding(
                db, binding=binding, portal=portal, config=config
            )
        if apply:
            await db.commit()
        print(f"{'已回填' if apply else '将回填'} {planned} 条 Binding")
    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="回填 Binding schedule 与 scheduler_jobs")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真正写库。默认只打印将要写入的 JSON。",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(apply=args.apply)))
