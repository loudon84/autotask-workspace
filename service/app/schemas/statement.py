"""对账单 API schemas。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import AliasChoices, Field

from app.schemas.common import CamelModel
from app.schemas.process import ProcessStageHistoryResponse, ProcessSubTaskResponse


class StatementQueryReceiptsRequest(CamelModel):
    portal_account_id: str = Field(
        validation_alias=AliasChoices("portal_account_id", "portalAccountId"),
        serialization_alias="portalAccountId",
    )
    date_start: str = Field(
        validation_alias=AliasChoices("date_start", "dateStart"),
        serialization_alias="dateStart",
    )
    date_end: str = Field(
        validation_alias=AliasChoices("date_end", "dateEnd"),
        serialization_alias="dateEnd",
    )


class StatementTaskResponse(CamelModel):
    task_id: str = Field(serialization_alias="taskId")
    status: str


class StatementQueryReceiptsResult(CamelModel):
    task_id: str = Field(serialization_alias="taskId")
    status: str
    run_status: str | None = Field(None, serialization_alias="runStatus")
    rows: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = Field(None, serialization_alias="errorMessage")


class StatementGenerateRequest(CamelModel):
    portal_account_id: str = Field(
        validation_alias=AliasChoices("portal_account_id", "portalAccountId"),
        serialization_alias="portalAccountId",
    )
    lines: list[dict[str, Any]]
    date_start: str | None = Field(
        None,
        validation_alias=AliasChoices("date_start", "dateStart"),
        serialization_alias="dateStart",
    )
    date_end: str | None = Field(
        None,
        validation_alias=AliasChoices("date_end", "dateEnd"),
        serialization_alias="dateEnd",
    )


class StatementGenerateResponse(CamelModel):
    ok: bool
    instance_id: str | None = Field(None, serialization_alias="instanceId")
    task_id: str | None = Field(None, serialization_alias="taskId")
    bill_id: str | None = Field(None, serialization_alias="billId")
    local_amount: str | None = Field(None, serialization_alias="localAmount")
    sdms_amount: str | None = Field(None, serialization_alias="sdmsAmount")
    sdms_check_head_id: str | None = Field(None, serialization_alias="sdmsCheckHeadId")
    sdms_check_num: str | None = Field(None, serialization_alias="sdmsCheckNum")


class StatementBillListItem(CamelModel):
    id: str
    process_instance_id: str = Field(serialization_alias="processInstanceId")
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    check_date: date = Field(serialization_alias="checkDate")
    check_amount: Decimal = Field(serialization_alias="checkAmount")
    check_status: str = Field(serialization_alias="checkStatus")
    invoice_status: str = Field(serialization_alias="invoiceStatus")
    invoice_no: str | None = Field(None, serialization_alias="invoiceNo")
    invoice_amount: Decimal | None = Field(None, serialization_alias="invoiceAmount")
    last_error: str | None = Field(None, serialization_alias="lastError")
    stage: str | None = None
    instance_status: str | None = Field(None, serialization_alias="instanceStatus")
    last_error_code: str | None = Field(None, serialization_alias="lastErrorCode")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class StatementBillDetail(StatementBillListItem):
    sdms_check_head_id: str | None = Field(None, serialization_alias="sdmsCheckHeadId")
    sdms_check_num: str | None = Field(None, serialization_alias="sdmsCheckNum")
    lines: list[dict[str, Any]] = Field(default_factory=list)
    sub_tasks: list[ProcessSubTaskResponse] = Field(
        default_factory=list, serialization_alias="subTasks"
    )
    stage_history: list[ProcessStageHistoryResponse] = Field(
        default_factory=list, serialization_alias="stageHistory"
    )
    scanned_file_paths: list[str] = Field(
        default_factory=list, serialization_alias="scannedFilePaths"
    )


class StatementInvoicePathsRequest(CamelModel):
    file_paths: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("file_paths", "filePaths"),
        serialization_alias="filePaths",
    )
