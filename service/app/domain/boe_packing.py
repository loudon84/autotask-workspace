"""京东方发票箱单 SOP constants."""

from app.models.enums import ProcessStage

# @lat: [[domain#BoeInvoicePacking]]
PROCESS_CODE = "srm_boe_invoice_packing"

VOL_UNIT = "立方米"
EXPECTED_ORG_CODE = "101"

ENRICH_TEMPLATE_CODE = "srm_boe_pack_enrich"
SAVE_DRAFT_TEMPLATE_CODE = "srm_boe_pack_save_draft"
SUBMIT_TEMPLATE_CODE = "srm_boe_pack_submit"

RPA_TEMPLATE_CODES = frozenset(
    {
        ENRICH_TEMPLATE_CODE,
        SAVE_DRAFT_TEMPLATE_CODE,
        SUBMIT_TEMPLATE_CODE,
    }
)

IN_FLIGHT_TASK_STATUSES = frozenset({"QUEUED", "LEASED", "RUNNING", "WAITING_HUMAN"})
BUSY_LEASE_STATUSES = frozenset({"LEASED", "RUNNING", "WAITING_HUMAN"})

MAIN_STAGES = [
    ProcessStage.BOE_PACK_SCAN_PLAN.value,
    ProcessStage.BOE_PACK_FETCH_WMS.value,
    ProcessStage.BOE_PACK_ENRICH.value,
    ProcessStage.BOE_PACK_SAVE_DRAFT.value,
    ProcessStage.BOE_PACK_REVIEW.value,
    ProcessStage.BOE_PACK_SUBMITTING.value,
    ProcessStage.BOE_PACK_SUBMITTED.value,
]

STAGE_DEFINITIONS = [
    {"id": ProcessStage.BOE_PACK_SCAN_PLAN.value, "name": "匹配交货计划", "button": None},
    {"id": ProcessStage.BOE_PACK_FETCH_WMS.value, "name": "读 WMS 装箱单", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_ENRICH.value, "name": "RPA 补全项目信息行", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_SAVE_DRAFT.value, "name": "保存 SRM 草稿单", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_REVIEW.value, "name": "客服核验", "button": "提交"},
    {"id": ProcessStage.BOE_PACK_SUBMITTING.value, "name": "提交 SRM 单据", "button": "重试"},
    {"id": ProcessStage.BOE_PACK_SUBMITTED.value, "name": "已完成", "button": None},
    {"id": ProcessStage.BOE_PACK_CANCELLED.value, "name": "已作废", "button": None},
]

RETRYABLE_STAGES = frozenset(
    {
        ProcessStage.BOE_PACK_FETCH_WMS.value,
        ProcessStage.BOE_PACK_ENRICH.value,
        ProcessStage.BOE_PACK_SAVE_DRAFT.value,
        ProcessStage.BOE_PACK_SUBMITTING.value,
    }
)

EDITABLE_STAGES = frozenset(
    {
        ProcessStage.BOE_PACK_REVIEW.value,
        ProcessStage.BOE_PACK_SAVE_DRAFT.value,
    }
)
