"""Portal-category documents live on Task disk, keyed by hardcoded category code."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.portal_category import CATEGORY_LABELS, PortalCategory, parse_portal_category
from app.models.base import not_deleted
from app.models.category_document import CategoryDocument
from app.models.user_cache import UserCache
from app.schemas.category_document import CategoryDocumentResponse, CategorySummary

ALLOWED_SUFFIXES = {
    ".doc",
    ".docx",
    ".pdf",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".zip",
}
MAX_BYTES = 20 * 1024 * 1024
MAX_FILES = 10
_UNSAFE_NAME = re.compile(r'[\x00-\x1f<>:"/\\|?*]')


def category_docs_root() -> Path:
    root = Path(settings.ARTIFACT_LOCAL_DIR) / "category-docs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(name: str) -> str:
    cleaned = _UNSAFE_NAME.sub("_", (name or "").strip()) or "document"
    return cleaned[:255]


def _suffix(name: str) -> str:
    return Path(name).suffix.lower()


def _content_disposition(filename: str) -> str:
    safe = _safe_filename(filename)
    ascii_name = safe.encode("ascii", "ignore").decode("ascii") or "document"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(safe)}"


def to_response(row: CategoryDocument) -> CategoryDocumentResponse:
    return CategoryDocumentResponse.model_validate(row)


async def list_categories(db: AsyncSession, tenant_id: str) -> list[CategorySummary]:
    counts: dict[str, int] = {}
    rows = (
        await db.execute(
            select(CategoryDocument.category, func.count(CategoryDocument.id))
            .where(
                CategoryDocument.tenant_id == tenant_id,
                not_deleted(CategoryDocument),
            )
            .group_by(CategoryDocument.category)
        )
    ).all()
    for code, total in rows:
        counts[str(code)] = int(total)
    return [
        CategorySummary(
            code=item.value,
            label=CATEGORY_LABELS[item],
            document_count=counts.get(item.value, 0),
        )
        for item in PortalCategory
    ]


async def list_documents(
    db: AsyncSession,
    tenant_id: str,
    category: str,
) -> list[CategoryDocument]:
    code = parse_portal_category(category, default_when_missing=False).value
    result = await db.execute(
        select(CategoryDocument)
        .where(
            CategoryDocument.tenant_id == tenant_id,
            CategoryDocument.category == code,
            not_deleted(CategoryDocument),
        )
        .order_by(CategoryDocument.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document(
    db: AsyncSession,
    tenant_id: str,
    category: str,
    document_id: str,
) -> CategoryDocument:
    code = parse_portal_category(category, default_when_missing=False).value
    row = (
        await db.execute(
            select(CategoryDocument).where(
                CategoryDocument.id == document_id,
                CategoryDocument.tenant_id == tenant_id,
                CategoryDocument.category == code,
                not_deleted(CategoryDocument),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(message="文档不存在", message_key="errors.autotask.category_document_not_found")
    return row


def absolute_path(row: CategoryDocument) -> Path:
    path = category_docs_root() / row.storage_key
    if not path.is_file():
        raise NotFoundError(message="文档文件不存在", message_key="errors.autotask.category_document_file_missing")
    return path


def download_headers(row: CategoryDocument) -> dict[str, str]:
    return {"Content-Disposition": _content_disposition(row.original_filename)}


def _validate_upload(filename: str, content: bytes) -> str:
    name = _safe_filename(filename)
    suffix = _suffix(name)
    if suffix not in ALLOWED_SUFFIXES:
        raise BadRequestError(
            message="不支持的文件类型",
            message_key="errors.autotask.category_document_type_unsupported",
        )
    if not content:
        raise BadRequestError(
            message="不能上传空文件",
            message_key="errors.autotask.category_document_empty",
        )
    if len(content) > MAX_BYTES:
        raise BadRequestError(
            message="单个文件不能超过 20MB",
            message_key="errors.autotask.category_document_too_large",
        )
    return name


async def save_uploads(
    db: AsyncSession,
    tenant_id: str,
    category: str,
    uploads: list[tuple[str, bytes]],
    *,
    actor: UserCache,
) -> list[CategoryDocument]:
    code = parse_portal_category(category, default_when_missing=False).value
    if not uploads:
        raise BadRequestError(
            message="请选择文件",
            message_key="errors.autotask.category_document_required",
        )
    if len(uploads) > MAX_FILES:
        raise BadRequestError(
            message=f"一次最多上传 {MAX_FILES} 个文件",
            message_key="errors.autotask.category_document_limit",
        )
    saved: list[CategoryDocument] = []
    actor_name = str(actor.name or "").strip()
    for filename, content in uploads:
        original = _validate_upload(filename, content)
        doc_id = str(uuid.uuid4())
        storage_key = f"{tenant_id}/{code}/{doc_id}{_suffix(original)}"
        dest = category_docs_root() / storage_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        row = CategoryDocument(
            id=doc_id,
            tenant_id=tenant_id,
            category=code,
            original_filename=original,
            storage_key=storage_key.replace("\\", "/"),
            byte_size=len(content),
            uploaded_by=actor.user_id,
            uploaded_by_name=actor_name,
        )
        db.add(row)
        saved.append(row)
    await db.commit()
    for row in saved:
        await db.refresh(row)
    return saved


async def delete_document(
    db: AsyncSession,
    tenant_id: str,
    category: str,
    document_id: str,
) -> None:
    row = await get_document(db, tenant_id, category, document_id)
    path = category_docs_root() / row.storage_key
    row.soft_delete()
    await db.commit()
    if path.is_file():
        path.unlink()
