from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import CamelModel


class BoePackingListItem(CamelModel):
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
    qty_mismatch: bool = Field(False, serialization_alias="qtyMismatch")
    invoice_no: str = Field("", serialization_alias="invoiceNo")
    factory: str = ""
    customer_name: str = Field("", serialization_alias="customerName")
    srm_draft_no: str = Field("", serialization_alias="srmDraftNo")
    header_id: str = Field("", serialization_alias="headerId")


class BoePackingHeaderPatch(CamelModel):
    invoice_no: str | None = Field(None, alias="invoiceNo")
    factory: str | None = None
    invoice_date: str | None = Field(None, alias="invoiceDate")
    etd: str | None = None
    consign_arrival_date: str | None = Field(None, alias="consignArrivalDate")
    total_vol: str | None = Field(None, alias="totalVol")


class BoePackingLinePatch(CamelModel):
    line_no: str | None = Field(None, alias="lineNo")
    po_num: str | None = Field(None, alias="poNum")
    item_num: str | None = Field(None, alias="itemNum")
    delivery_qty: str | None = Field(None, alias="deliveryQty")
    net_weight: str | None = Field(None, alias="netWeight")
    net_weight_unit: str | None = Field(None, alias="netWeightUnit")
    region_code: str | None = Field(None, alias="regionCode")
    region_srm_name: str | None = Field(None, alias="regionSrmName")
    line_item: str | None = Field(None, alias="lineItem")
    order_qty: str | None = Field(None, alias="orderQty")
    order_unit: str | None = Field(None, alias="orderUnit")
    remaining_qty: str | None = Field(None, alias="remainingQty")
    item_name: str | None = Field(None, alias="itemName")
    factory: str | None = None


class BoePackingAttachmentPatch(CamelModel):
    id: str | None = None
    type: str | None = None
    file_name: str | None = Field(None, alias="fileName")
    file_path: str | None = Field(None, alias="filePath")


class BoePackingPatchRequest(CamelModel):
    header: BoePackingHeaderPatch | None = None
    lines: list[BoePackingLinePatch] | None = None
    attachments: list[BoePackingAttachmentPatch] | None = None


class BoeMatchResponse(CamelModel):
    created_count: int = Field(serialization_alias="createdCount")
    skipped_count: int = Field(serialization_alias="skippedCount")
    missing_portal: list[str] = Field(default_factory=list, serialization_alias="missingPortal")
    error: str | None = None
    created_ids: list[str] = Field(default_factory=list, serialization_alias="createdIds")
    skipped: list[dict[str, Any]] = Field(default_factory=list)
