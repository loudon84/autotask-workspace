"""门户分类文档：绑硬编码 category code，文件落 Task 盘。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.portal_category import INVALID_CATEGORY_MESSAGE_KEY
from app.models.user_cache import UserCache
from app.services import category_document_service as svc


def _user() -> UserCache:
    return UserCache(
        user_id="user-001",
        name="测试用户",
        email="user@example.com",
        current_org_id="tenant-001",
        org_role="member",
        synced_at=datetime.now(UTC),
    )


def _scalars_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_list_categories_includes_hardcoded_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock()
    grouped = MagicMock()
    grouped.all.return_value = [("TIANDI", 2)]
    db.execute = AsyncMock(return_value=grouped)
    rows = await svc.list_categories(db, "tenant-001")
    assert [item.code for item in rows] == ["TIANDI", "BOE"]
    assert rows[0].label == "天地伟业"
    assert rows[0].document_count == 2
    assert rows[1].label == "京东方"
    assert rows[1].document_count == 0


@pytest.mark.asyncio
async def test_list_documents_rejects_unknown_category() -> None:
    db = MagicMock()
    with pytest.raises(BadRequestError) as exc_info:
        await svc.list_documents(db, "tenant-001", "ACME")
    assert exc_info.value.message_key == INVALID_CATEGORY_MESSAGE_KEY


@pytest.mark.asyncio
async def test_save_and_delete_writes_task_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(svc.settings, "ARTIFACT_LOCAL_DIR", str(tmp_path))
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    rows = await svc.save_uploads(
        db,
        "tenant-001",
        "TIANDI",
        [("AutoTask天地伟业操作手册.doc", b"%DOC")],
        actor=_user(),
    )
    assert len(rows) == 1
    stored = tmp_path / "category-docs" / rows[0].storage_key
    assert stored.is_file()
    assert stored.read_bytes() == b"%DOC"
    assert rows[0].original_filename == "AutoTask天地伟业操作手册.doc"
    assert rows[0].category == "TIANDI"

    existing = rows[0]
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
    )
    existing.soft_delete = MagicMock()
    await svc.delete_document(db, "tenant-001", "TIANDI", existing.id)
    existing.soft_delete.assert_called_once()
    assert not stored.exists()


@pytest.mark.asyncio
async def test_save_rejects_exe(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(svc.settings, "ARTIFACT_LOCAL_DIR", str(tmp_path))
    db = MagicMock()
    with pytest.raises(BadRequestError) as exc_info:
        await svc.save_uploads(
            db,
            "tenant-001",
            "BOE",
            [("payload.exe", b"MZ")],
            actor=_user(),
        )
    assert exc_info.value.message_key == "errors.autotask.category_document_type_unsupported"


@pytest.mark.asyncio
async def test_get_document_missing() -> None:
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    with pytest.raises(NotFoundError):
        await svc.get_document(db, "tenant-001", "TIANDI", "missing")
