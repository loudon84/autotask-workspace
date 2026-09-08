"""京东方定时器入口：到点做什么写在这里，调度内核只负责 notify。

- boe.pack_match：对拥有京东方门户账号的每个租户跑一轮匹配交货计划
  （租户级一次 HTTP，不按门户复制定时器）
- boe.srm_login：按门户 loginAccount 去重后晨间登录（RPA 尚未接入时只核对目标）

开关与 cron 在调度中心维护（timers 表），本模块不含调度循环。
"""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import select

from app.core.deps import async_session_factory
from app.domain.boe_srm_login import collect_boe_srm_login_targets
from app.domain.portal_category import PortalCategory
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.services import boe_packing_service

logger = logging.getLogger(__name__)

BOE_PACK_MATCH_TARGET = "boe.pack_match"
BOE_SRM_LOGIN_TARGET = "boe.srm_login"


async def pack_match_due() -> None:
    """到点：逐租户匹配交货计划；单租户失败不影响其他租户。"""
    async with async_session_factory() as db:
        tenants = list(
            (
                await db.execute(
                    select(PortalAccount.tenant_id)
                    .where(
                        PortalAccount.category == PortalCategory.BOE.value,
                        not_deleted(PortalAccount),
                    )
                    .distinct()
                )
            ).scalars().all()
        )
        created = 0
        for tenant_id in tenants:
            try:
                result = await boe_packing_service.match_delivery_plans(
                    db, tenant_id, actor="timer:boe.pack_match"
                )
                created += int(result.get("created_count") or 0)
            except Exception:
                logger.exception("京东方匹配失败 tenant=%s", tenant_id)
                await db.rollback()
        logger.info("定时京东方匹配到点：新建 %d 单（租户 %d 个）", created, len(tenants))


async def srm_login_due() -> None:
    """到点：按门户去重核对晨间登录目标。CAS 打码 RPA 尚未接入，本轮不打开浏览器。"""
    async with async_session_factory() as db:
        portals = list(
            (
                await db.execute(
                    select(PortalAccount).where(not_deleted(PortalAccount))
                )
            ).scalars().all()
        )
        by_tenant: dict[str, list[PortalAccount]] = defaultdict(list)
        for row in portals:
            by_tenant[str(row.tenant_id)].append(row)
        total = 0
        problems = 0
        for tenant_id, rows in by_tenant.items():
            result = collect_boe_srm_login_targets(rows)
            total += len(result.targets)
            problems += len(result.errors)
            for err in result.errors:
                logger.warning("京东方晨间登录配置 tenant=%s %s", tenant_id, err)
            if result.targets:
                logger.info(
                    "京东方晨间登录到点 tenant=%s accounts=%d rpa=not_wired",
                    tenant_id,
                    len(result.targets),
                )
        logger.info(
            "京东方晨间登录汇总 accounts=%d errors=%d（RPA 尚未接入，未登录 SRM）",
            total,
            problems,
        )
