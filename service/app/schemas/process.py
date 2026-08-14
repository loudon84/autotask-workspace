from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field, field_validator

from app.schemas.common import CamelModel
from app.services.json_utils import loads_json


class ProcessInstanceListItem(CamelModel):
    id: str
    process_code: str = Field(serialization_alias="processCode")
    biz_key: str = Field(serialization_alias="bizKey")
    title: str
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    stage: str
    status: str
    line_total: int = Field(serialization_alias="lineTotal")
    line_done: int = Field(serialization_alias="lineDone")
    last_error_code: str | None = Field(None, serialization_alias="lastErrorCode")
    last_error_message: str | None = Field(None, serialization_alias="lastErrorMessage")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ProcessLineItemResponse(CamelModel):
    id: str
    line_number: str = Field(serialization_alias="lineNumber")
    material_number: str = Field(serialization_alias="materialNumber")
    item_name: str | None = Field(None, serialization_alias="itemName")
    item_specification: str | None = Field(None, serialization_alias="itemSpecification")
    material_status: str | None = Field(None, serialization_alias="materialStatus")
    internal_code: str | None = Field(None, serialization_alias="internalCode")
    order_quantity: str | None = Field(None, serialization_alias="orderQuantity")
    order_quantity_uom: str | None = Field(None, serialization_alias="orderQuantityUom")
    unit_selling_price: str | None = Field(None, serialization_alias="unitSellingPrice")
    tax_included_amount: str | None = Field(None, serialization_alias="taxIncludedAmount")
    request_date: str | None = Field(None, serialization_alias="requestDate")
    standard_delivery_days: str | None = Field(None, serialization_alias="standardDeliveryDays")
    meets_lead_time: str | None = Field(None, serialization_alias="meetsLeadTime")
    supplier_delivery_date: str | None = Field(None, serialization_alias="supplierDeliveryDate")
    outstanding_quantity: str | None = Field(None, serialization_alias="outstandingQuantity")
    remarks: str | None = None
    direct_shipment_remarks: str | None = Field(None, serialization_alias="directShipmentRemarks")
    expected_delivery_date: str | None = Field(None, serialization_alias="expectedDeliveryDate")
    line_status: str = Field(serialization_alias="lineStatus")
    sub_task_id: str | None = Field(None, serialization_alias="subTaskId")
    last_error_code: str | None = Field(None, serialization_alias="lastErrorCode")
    last_error_message: str | None = Field(None, serialization_alias="lastErrorMessage")


class ProcessStageHistoryResponse(CamelModel):
    id: str
    from_stage: str | None = Field(None, serialization_alias="fromStage")
    to_stage: str = Field(serialization_alias="toStage")
    actor: str
    note: str | None = None
    created_at: datetime = Field(serialization_alias="createdAt")


class ProcessSubTaskResponse(CamelModel):
    id: str
    title: str
    task_type: str = Field(serialization_alias="taskType")
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    line_number: str | None = Field(None, serialization_alias="lineNumber")


class ProcessInstanceDetail(ProcessInstanceListItem):
    summary: dict[str, Any] = Field(default_factory=dict)
    lines: list[ProcessLineItemResponse] = Field(default_factory=list)
    stage_history: list[ProcessStageHistoryResponse] = Field(
        default_factory=list, serialization_alias="stageHistory"
    )
    sub_tasks: list[ProcessSubTaskResponse] = Field(default_factory=list, serialization_alias="subTasks")

    @field_validator("summary", mode="before")
    @classmethod
    def parse_summary(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            return loads_json(value, {})
        return value or {}


class ProcessLineDateSubmit(CamelModel):
    expected_delivery_date: str = Field(
        validation_alias=AliasChoices("expected_delivery_date", "expectedDeliveryDate"),
        serialization_alias="expectedDeliveryDate",
    )


class ProcessScanRequest(CamelModel):
    portal_account_id: str = Field(
        validation_alias=AliasChoices("portal_account_id", "portalAccountId"),
        serialization_alias="portalAccountId",
    )


class ProcessScanResponse(CamelModel):
    task_id: str = Field(serialization_alias="taskId")
    status: str


class ProcessSignPollRunResponse(CamelModel):
    candidate_count: int = Field(serialization_alias="candidateCount")
    created_count: int = Field(serialization_alias="createdCount")


class ProcessCreateFromScanResponse(CamelModel):
    created_count: int = Field(serialization_alias="createdCount")
    instance_ids: list[str] = Field(serialization_alias="instanceIds")
