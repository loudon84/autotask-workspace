"""WMS region_code → SRM display name."""

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.portal_category import parse_portal_category
from app.models.base import not_deleted
from app.models.region_code_map import RegionCodeMap
from app.models.user_cache import UserCache

TABLE_MISSING_MESSAGE = "地区对照表尚未迁库，请先授权执行 Alembic b2d4f6a81935"
TABLE_MISSING_KEY = "errors.autotask.region_map_table_missing"


async def list_maps(db: AsyncSession, tenant_id: str, category: str) -> list[RegionCodeMap]:
    code = parse_portal_category(category, default_when_missing=False).value
    try:
        result = await db.execute(
            select(RegionCodeMap)
            .where(
                RegionCodeMap.tenant_id == tenant_id,
                RegionCodeMap.category == code,
                not_deleted(RegionCodeMap),
            )
            .order_by(RegionCodeMap.region_code.asc())
        )
        return list(result.scalars().all())
    except ProgrammingError:
        await db.rollback()
        return []


async def mapping_dict(db: AsyncSession, tenant_id: str, category: str) -> dict[str, str]:
    rows = await list_maps(db, tenant_id, category)
    return {row.region_code: row.srm_display_name for row in rows}


async def upsert_map(
    db: AsyncSession,
    tenant_id: str,
    *,
    category: str,
    region_code: str,
    srm_display_name: str,
    actor: UserCache,
) -> RegionCodeMap:
    code = parse_portal_category(category, default_when_missing=False).value
    region = region_code.strip()
    name = srm_display_name.strip()
    if not region or not name:
        raise BadRequestError(
            message="地区编号和 SRM 名称都不能为空",
            message_key="errors.autotask.region_map_invalid",
        )
    try:
        existing = (
            await db.execute(
                select(RegionCodeMap).where(
                    RegionCodeMap.tenant_id == tenant_id,
                    RegionCodeMap.category == code,
                    RegionCodeMap.region_code == region,
                    not_deleted(RegionCodeMap),
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = RegionCodeMap(
                tenant_id=tenant_id,
                category=code,
                region_code=region,
                srm_display_name=name,
                updated_by=actor.user_id,
                updated_by_name=actor.name or "",
            )
            db.add(existing)
        else:
            existing.srm_display_name = name
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
