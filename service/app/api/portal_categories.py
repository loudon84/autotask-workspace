"""门户分类文档 API。分类码写死，库只存 code。"""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.category_document import CategoryDocumentResponse, CategorySummary
from app.schemas.common import ApiResponse
from app.services import category_document_service as svc

router = APIRouter()


@router.get("", response_model=ApiResponse[list[CategorySummary]])
async def list_portal_categories(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    return ApiResponse(data=await svc.list_categories(db, tenant_id))


@router.get("/{category}/documents", response_model=ApiResponse[list[CategoryDocumentResponse]])
async def list_category_documents(
    category: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    rows = await svc.list_documents(db, tenant_id, category)
    return ApiResponse(data=[svc.to_response(row) for row in rows])


@router.post("/{category}/documents", response_model=ApiResponse[list[CategoryDocumentResponse]])
async def upload_category_documents(
    category: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    uploads: list[tuple[str, bytes]] = []
    for index, upload in enumerate(files):
        name = upload.filename or f"document-{index}"
        content = await upload.read()
        uploads.append((name, content))
    rows = await svc.save_uploads(db, tenant_id, category, uploads, actor=user)
    return ApiResponse(data=[svc.to_response(row) for row in rows])


@router.get("/{category}/documents/{document_id}/file")
async def download_category_document(
    category: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    row = await svc.get_document(db, tenant_id, category, document_id)
    path = svc.absolute_path(row)
    return FileResponse(
        path,
        filename=row.original_filename,
        headers=svc.download_headers(row),
    )


@router.delete("/{category}/documents/{document_id}", response_model=ApiResponse[None])
async def delete_category_document(
    category: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await svc.delete_document(db, tenant_id, category, document_id)
    return ApiResponse(data=None, message="已删除")
