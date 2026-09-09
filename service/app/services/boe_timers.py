"""京东方定时器入口：到点做什么写在这里，调度内核只负责 notify。

- boe.pack_match：对拥有京东方门户账号的每个租户跑一轮匹配交货计划
- boe.srm_login：IMAP 就绪后按门户 loginAccount 去重，串行派薄登录 RPA
"""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import select

from app.core.deps import async_session_factory
from app.domain.boe_srm_login import collect_boe_srm_login_targets
from app.domain.portal_category import PortalCategory
from app.integrations.imap_mail import MailImapError
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount
from app.services import boe_packing_service
from app.services import boe_srm_login_service as login_svc
from app.services import mail_otp_service
from app.services.timer_registry import TimerBusinessError

logger = logging.getLogger(__name__)

BOE_PACK_MATCH_TARGET = "boe.pack_match"
BOE_SRM_LOGIN_TARGET = "boe.srm_login"


async def pack_match_due() -> str:
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
        summary = f"新建 {created} 单（租户 {len(tenants)} 个）"
        logger.info("定时京东方匹配到点：%s", summary)
        return summary


async def srm_login_due() -> str:
    """到点：核对 IMAP，再按去重账号串行登录。摘要写入 timer_runs，禁止写验证码。"""
    try:
        await mail_otp_service.assert_imap_ready()
    except MailImapError as exc:
        raise TimerBusinessError(str(exc)) from exc

    async with async_session_factory() as db:
        portals = list(
            (
                await db.execute(
                    select(PortalAccount).where(not_deleted(PortalAccount))
                )
            ).scalars().all()
        )
    by_tenant: dict[str, list[PortalAccount]] = defaultdict(list)
    by_id = {str(row.id): row for row in portals}
    for row in portals:
        by_tenant[str(row.tenant_id)].append(row)

    lines: list[str] = []
    any_fail = False
    for tenant_id, rows in by_tenant.items():
        collected = collect_boe_srm_login_targets(rows)
        for err in collected.errors:
            lines.append(err)
            any_fail = True
        for target in collected.targets:
            portal = by_id.get(target.sample_portal_id)
            if portal is None:
                lines.append(f"{target.login_account} 失败：门户不存在")
                any_fail = True
                continue
            async with async_session_factory() as db:
                result = await login_svc.login_one_account(
                    db,
                    tenant_id=tenant_id,
                    portal=portal,
                    target=target,
                    actor="timer:boe.srm_login",
                )
            lines.append(f"{target.login_account} {result}")
            if result != "成功":
                any_fail = True
    summary = login_svc.summarize_login_wave(lines, any_fail=any_fail)
    logger.info("京东方晨间登录汇总 %s", summary)
    return summary
