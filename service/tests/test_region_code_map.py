"""Region map validation before the table is migrated."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import ProgrammingError

from app.core.exceptions import BadRequestError
from app.models.region_code_map import RegionCodeMap
from app.models.user_cache import UserCache
from app.services import region_code_map_service
from app.services.region_code_map_service import list_maps, mapping_dict, upsert_map


def _user() -> UserCache:
    return UserCache(
        user_id="user-1",
        name="客服",
        email="cs@example.com",
        current_org_id="tenant-1",
        org_role="member",
        synced_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_upsert_rejects_blank_code() -> None:
    with pytest.raises(BadRequestError) as exc_info:
        await upsert_map(
            MagicMock(),
            "tenant-1",
            region_code="  ",
            default_name="中国台湾",
            actor=_user(),
        )
    assert exc_info.value.message_key == "errors.autotask.region_map_invalid"


@pytest.mark.asyncio
async def test_upsert_rejects_blank_default_name() -> None:
    with pytest.raises(BadRequestError) as exc_info:
        await upsert_map(
            MagicMock(),
            "tenant-1",
            region_code="TAIWAN,CHINA",
            default_name=" ",
            actor=_user(),
        )
    assert exc_info.value.message_key == "errors.autotask.region_map_invalid"


class _Nested:
    """begin_nested 替代品：进入无操作，异常照常抛出。"""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_list_maps_missing_table_does_not_rollback_session() -> None:
    """表未迁时报 ProgrammingError：返回空且只用 SAVEPOINT，绝不 db.rollback() 整个会话
    （调用方事务里可能已有待提交业务数据，如京东方匹配新建的实例）。"""
    db = MagicMock()
    db.begin_nested = MagicMock(return_value=_Nested())
    db.execute = AsyncMock(
        side_effect=ProgrammingError("select", {}, Exception("undefined_table"))
    )
    db.rollback = AsyncMock()
    rows = await list_maps(db, "tenant-1")
    assert rows == []
    db.rollback.assert_not_awaited()


def _row(code: str, default: str, boe: str | None) -> RegionCodeMap:
    return RegionCodeMap(
        tenant_id="tenant-1",
        region_code=code,
        default_name=default,
        boe_name=boe,
        updated_by="user-1",
    )


def _db_returning(existing: RegionCodeMap | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_upsert_creates_new_row() -> None:
    """走通查询路径：db.execute 必须先 await 再取 scalar（防括号优先级回归，
    曾写成 await db.execute(...).scalar_one_or_none() 导致保存 500）。"""
    db = _db_returning(None)
    row = await upsert_map(
        db,
        "tenant-1",
        region_code="TAIWAN,CHINA",
        default_name="中国台湾",
        actor=_user(),
    )
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    assert row.region_code == "TAIWAN,CHINA"
    assert row.default_name == "中国台湾"
    assert row.boe_name is None


@pytest.mark.asyncio
async def test_upsert_updates_existing_row() -> None:
    db = _db_returning(_row("TAIWAN,CHINA", "台湾", None))
    row = await upsert_map(
        db,
        "tenant-1",
        region_code="TAIWAN,CHINA",
        default_name="中国台湾",
        boe_name="台湾",
        actor=_user(),
    )
    db.add.assert_not_called()
    db.commit.assert_awaited_once()
    assert row.default_name == "中国台湾"
    assert row.boe_name == "台湾"


@pytest.mark.asyncio
async def test_mapping_dict_boe_prefers_boe_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """京东方：boe_name 有值用 boe_name，空则回退默认名。"""
    rows = [
        _row("TAIWAN,CHINA", "中国台湾", None),
        _row("CHINA", "中国", "中国大陆"),
    ]
    monkeypatch.setattr(
        region_code_map_service, "list_maps", AsyncMock(return_value=rows)
    )
    result = await mapping_dict(MagicMock(), "tenant-1", "BOE")
    assert result == {"TAIWAN,CHINA": "中国台湾", "CHINA": "中国大陆"}


@pytest.mark.asyncio
async def test_mapping_dict_other_category_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没有专列的分类（如天地伟业）一律读默认名，不用逐行维护。"""
    rows = [_row("TAIWAN,CHINA", "中国台湾", "台湾")]
    monkeypatch.setattr(
        region_code_map_service, "list_maps", AsyncMock(return_value=rows)
    )
    result = await mapping_dict(MagicMock(), "tenant-1", "TIANDI")
    assert result == {"TAIWAN,CHINA": "中国台湾"}
