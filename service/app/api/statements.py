"""天地伟业对账单 API。"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.security import bearer_scheme, get_current_user, require_portal_visible, require_tenant_access
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import PortalPermission
from app.models.rpa_run import RpaRun
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.statement import (
    StatementBillDetail,
    StatementBillListItem,
    StatementGenerateRequest,
    StatementGenerateResponse,
    StatementInvoicePathsRequest,
    StatementQueryReceiptsRequest,
    StatementQueryReceiptsResult,
    StatementTaskResponse,
)
from app.services import process_instance_service, statement_service
from app.services.permission_service import list_accessible_portal_ids
from app.services.user_sync import resolve_login_username

router = APIRouter()

_ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".ofd"}
_MAX_FILES = 10
_MAX_BYTES = 20 * 1024 * 1024


async def _require_bill_visible(
    db: AsyncSession, user: UserCache, tenant_id: str, bill_id: str
):
    bill = await statement_service.get_bill(db, tenant_id, bill_id)
    await require_portal_visible(db, user, bill.portal_account_id)
    return bill


@router.post("/query-receipts", response_model=ApiResponse[StatementTaskResponse])
async def query_receipts(
    body: StatementQueryReceiptsRequest,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await require_portal_visible(db, user, body.portal_account_id)
    task = await statement_service.query_receipts(
        db,
        tenant_id,
        body.portal_account_id,
        body.date_start,
        body.date_end,
        actor=user.user_id,
    )
    return ApiResponse(data=StatementTaskResponse(task_id=task.id, status=task.status))


@router.get("/query-receipts/{task_id}", response_model=ApiResponse[StatementQueryReceiptsResult])
async def get_query_receipts_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = (
        await db.execute(
            select(AutomationTask).where(
                AutomationTask.id == task_id,
                AutomationTask.tenant_id == tenant_id,
                not_deleted(AutomationTask),
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="查询任务不存在", message_key="errors.autotask.task_not_found")
    await require_portal_visible(db, user, task.portal_account_id)
    run = (
        await db.execute(
            select(RpaRun)
            .where(RpaRun.task_id == task.id, not_deleted(RpaRun))
            .order_by(RpaRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    rows: list[dict] = []
    run_status = None
    error_message = None
    if run is not None:
        run_status = run.status
        error_message = run.error_message
        output = run.output if isinstance(run.output, dict) else {}
        raw_rows = output.get("rows")
        if isinstance(raw_rows, list):
            rows = [row for row in raw_rows if isinstance(row, dict)]
    return ApiResponse(
        data=StatementQueryReceiptsResult(
            task_id=task.id,
            status=task.status,
            run_status=run_status,
            rows=rows,
            error_message=error_message,
        )
    )


@router.post("/generate", response_model=ApiResponse[StatementGenerateResponse])
async def generate_statement(
    body: StatementGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await require_portal_visible(db, user, body.portal_account_id)
    result = await statement_service.generate_statement(
        db,
        tenant_id,
        body.portal_account_id,
        body.lines,
        actor=user.user_id,
        date_start=body.date_start,
        date_end=body.date_end,
    )
    return ApiResponse(data=StatementGenerateResponse.model_validate(result))


@router.post("/{bill_id}/retry-generate", response_model=ApiResponse[StatementGenerateResponse])
async def retry_generate(
    bill_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    bill = await _require_bill_visible(db, user, tenant_id, bill_id)
    result = await statement_service.retry_generate(db, tenant_id, bill_id, actor=user.user_id)
    return ApiResponse(data=StatementGenerateResponse.model_validate(result))


@router.get("", response_model=ApiResponse[list[StatementBillListItem]])
async def list_statements(
    check_status: str | None = None,
    stage: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    accessible_ids = await list_accessible_portal_ids(
        db, user, tenant_id, PortalPermission.PORTAL_VIEW
    )
    rows = await statement_service.list_bills(
        db,
        tenant_id,
        check_status=check_status,
        stage=stage,
        accessible_portal_ids=accessible_ids,
    )
    return ApiResponse(
        data=[statement_service.to_list_item(bill, instance) for bill, instance in rows]
    )


@router.get("/{bill_id}", response_model=ApiResponse[StatementBillDetail])
async def get_statement(
    bill_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    bill = await _require_bill_visible(db, user, tenant_id, bill_id)
    instance = await statement_service.get_bill_instance(db, bill.process_instance_id)
    sub_tasks = await process_instance_service.list_sub_tasks(db, bill.process_instance_id)
    history = await process_instance_service.list_stage_history(db, bill.process_instance_id)
    detail = statement_service.to_detail(
        bill,
        instance,
        sub_tasks=[process_instance_service.to_sub_task_response(task) for task in sub_tasks],
        stage_history=history,
    )
    return ApiResponse(data=detail)


async def _save_upload_files(bill_id: str, files: list[UploadFile]) -> list[str]:
    if not files:
        raise BadRequestError(
            message="请选择发票文件",
            message_key="errors.autotask.statement.invoice_files_required",
        )
    if len(files) > _MAX_FILES:
        raise BadRequestError(
            message="最多上传 10 个发票文件",
            message_key="errors.autotask.statement.invoice_files_limit",
        )
    root = Path(settings.ARTIFACT_LOCAL_DIR) / "statements" / bill_id
    root.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for index, upload in enumerate(files):
        name = upload.filename or f"invoice-{index}"
        suffix = Path(name).suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise BadRequestError(
                message=f"不支持的文件格式: {suffix or name}",
                message_key="errors.autotask.statement.invoice_file_type",
            )
        content = await upload.read()
        if len(content) > _MAX_BYTES:
            raise BadRequestError(
                message=f"单个文件不能超过 20M: {name}",
                message_key="errors.autotask.statement.invoice_file_size",
            )
        target = root / f"{index:02d}_{Path(name).name}"
        target.write_bytes(content)
        saved.append(str(target.resolve()))
    return saved


@router.post("/{bill_id}/invoice", response_model=ApiResponse[StatementTaskResponse])
async def upload_invoice_files(
    bill_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await _require_bill_visible(db, user, tenant_id, bill_id)
    file_paths = await _save_upload_files(bill_id, files)
    task = await statement_service.upload_invoice(
        db, tenant_id, bill_id, file_paths=file_paths, actor=user.user_id
    )
    return ApiResponse(data=StatementTaskResponse(task_id=task.id, status=task.status))


@router.post("/{bill_id}/invoice/paths", response_model=ApiResponse[StatementTaskResponse])
async def upload_invoice_paths(
    bill_id: str,
    body: StatementInvoicePathsRequest,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await _require_bill_visible(db, user, tenant_id, bill_id)
    task = await statement_service.upload_invoice(
        db, tenant_id, bill_id, file_paths=body.file_paths, actor=user.user_id
    )
    return ApiResponse(data=StatementTaskResponse(task_id=task.id, status=task.status))


@router.post("/{bill_id}/submit-review", response_model=ApiResponse[StatementTaskResponse])
async def submit_review(
    bill_id: str,
    body: StatementInvoicePathsRequest,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    tenant_id = require_tenant_access(user)
    await _require_bill_visible(db, user, tenant_id, bill_id)
    username = await resolve_login_username(
        credentials.credentials if credentials else None,
        user,
    )
    task = await statement_service.submit_review(
        db,
        tenant_id,
        bill_id,
        file_paths=body.file_paths,
        actor=user.user_id,
        sdms_username=username,
    )
    return ApiResponse(data=StatementTaskResponse(task_id=task.id, status=task.status))


@router.post("/{bill_id}/cancel", response_model=ApiResponse[StatementBillListItem])
async def cancel_statement(
    bill_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    await _require_bill_visible(db, user, tenant_id, bill_id)
    bill = await statement_service.cancel_statement(db, tenant_id, bill_id, actor=user.user_id)
    return ApiResponse(data=StatementBillListItem.model_validate(bill))
