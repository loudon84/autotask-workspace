"""地区编号宽表：code 共用，default_name 兜底，SRM 专列（boe_name）可空。"""

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.portal_category import PortalCategory, parse_portal_category
from app.models.base import not_deleted
from app.models.region_code_map import RegionCodeMap
from app.models.user_cache import UserCache

TABLE_MISSING_MESSAGE = "地区对照表尚未迁库，请先授权执行 Alembic b2d4f6a81935"
TABLE_MISSING_KEY = "errors.autotask.region_map_table_missing"


def _display_name(row: RegionCodeMap, category: PortalCategory) -> str:
    """按门户分类取名：专列有值用专列，空则回退默认名。无专列的分类一律默认名。"""
    if category is PortalCategory.BOE:
        specific = (row.boe_name or "").strip()
        if specific:
            return specific
    return row.default_name


async def list_maps(db: AsyncSession, tenant_id: str) -> list[RegionCodeMap]:
    try:
        # SAVEPOINT 隔离：表未迁时只回滚这条查询，不能 db.rollback() 整个会话——
        # 调用方（如京东方匹配）事务里可能已有待提交的业务数据
        async with db.begin_nested():
            result = await db.execute(
                select(RegionCodeMap)
                .where(
                    RegionCodeMap.tenant_id == tenant_id,
                    not_deleted(RegionCodeMap),
                )
                .order_by(RegionCodeMap.region_code.asc())
            )
            return list(result.scalars().all())
    except ProgrammingError:
        return []


async def mapping_dict(db: AsyncSession, tenant_id: str, category: str) -> dict[str, str]:
    code = parse_portal_category(category, default_when_missing=False)
    rows = await list_maps(db, tenant_id)
    return {row.region_code: _display_name(row, code) for row in rows}


async def upsert_map(
    db: AsyncSession,
    tenant_id: str,
    *,
    region_code: str,
    default_name: str,
    boe_name: str | None = None,
    actor: UserCache,
) -> RegionCodeMap:
    region = region_code.strip()
    default = default_name.strip()
    boe = (boe_name or "").strip() or None
    if not region or not default:
        raise BadRequestError(
            message="地区编号和默认显示名都不能为空",
            message_key="errors.autotask.region_map_invalid",
        )
    try:
        existing = (
            await db.execute(
                select(RegionCodeMap).where(
                    RegionCodeMap.tenant_id == tenant_id,
                    RegionCodeMap.region_code == region,
                    not_deleted(RegionCodeMap),
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = RegionCodeMap(
                tenant_id=tenant_id,
                region_code=region,
                default_name=default,
                boe_name=boe,
                updated_by=actor.user_id,
                updated_by_name=actor.name or "",
            )
            db.add(existing)
        else:
            existing.default_name = default
            existing.boe_name = boe
            existing.updated_by = actor.user_id
            existing.updated_by_name = actor.name or ""
        await db.commit()
        await db.refresh(existing)
    except ProgrammingError:
        await db.rollback()
        raise BadRequestError(
            message=TABLE_MISSING_MESSAGE,
            message_key=TABLE_MISSING_KEY,
        ) from None
    return existing


async def delete_map(db: AsyncSession, tenant_id: str, map_id: str) -> None:
    row = (
        await db.execute(
            select(RegionCodeMap).where(
                RegionCodeMap.id == map_id,
                RegionCodeMap.tenant_id == tenant_id,
                not_deleted(RegionCodeMap),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(message="地区映射不存在", message_key="errors.autotask.region_map_not_found")
    row.soft_delete()
    await db.commit()
