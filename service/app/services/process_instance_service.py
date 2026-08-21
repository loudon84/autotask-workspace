"""流程实例（SOP 主任务）业务服务。

对应 project-docs/prd/v2.01客户订单-业务需求.md（现行）；设计定稿见 v2.0：
- 主任务按固定节点推进，客服只看流程实例
- 子任务为各节点背后的 RPA 执行单元（automation_tasks + rpa_runs）
- 子任务失败不回滚；节点1（建单）失败即整单失败
"""

import re
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import (
    BindingStatus,
    PortalAccountStatus,
    ProcessInstanceStatus,
    ProcessLineStatus,
    ProcessStage,
    RunStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.portal_account import PortalAccount
from app.models.process_instance import ProcessInstance
from app.models.process_line_item import ProcessLineItem
from app.models.process_stage_history import ProcessStageHistory
from app.models.rpa_run import RpaRun
from app.models.user_cache import UserCache
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json, loads_json
from app.services.process_error_messages import localize_process_error
from app.services.user_sync import username_from_user_cache

PROCESS_CODE_SRM_CUSTOMER_ORDER = "srm_customer_order"
PROCESS_CODE_SRM_TIANDI_STATEMENT = "srm_tiandi_statement"

SCAN_TASK_TYPE = "srm_scan_pending_orders"
CREATE_SDMS_TEMPLATE_CODE = "srm_prepare_erp_order"
FILL_LINE_DATE_TEMPLATE_CODE = "srm_fill_line_delivery_date"
SIGN_TEMPLATE_CODE = "srm_sign_order"
CHECK_REPLY_TEMPLATE_CODE = "srm_check_reply_status"
ARCHIVE_TEMPLATE_CODE = "srm_upload_order_attachment"

STMT_QUERY_RECEIPTS_TEMPLATE_CODE = "srm_stmt_query_receipts"
STMT_GENERATE_TEMPLATE_CODE = "srm_stmt_generate"
STMT_UPLOAD_INVOICE_TEMPLATE_CODE = "srm_stmt_upload_invoice"
STMT_SUBMIT_REVIEW_TEMPLATE_CODE = "srm_stmt_submit_review"

SCAN_OUTPUT_SCHEMA = "SRM_PENDING_ORDERS_OUTPUT_V1"
SIGNED_REPLY_STATUS = "已回签"

# 归档上传 SDMS 的 username：有登录人用登录工号；轮询无登录人时用实例创建人；
# 创建人也没有时用此固定工号。该字段 SDMS 只要求非空，值不敏感。
_FALLBACK_ARCHIVE_SDMS_USERNAME = "SMC-SZ-HR15563"
_DEMO_PORTAL_HOST = "192.168.102.247"

_ARCHIVE_SKIP_STATUSES = {
    TaskStatus.QUEUED.value,
    TaskStatus.RUNNING.value,
    TaskStatus.WAITING_HUMAN.value,
    TaskStatus.SUCCESS.value,
    TaskStatus.SUCCESS_MANUAL.value,
}
_CHECK_REPLY_IN_FLIGHT = {
    TaskStatus.QUEUED.value,
    TaskStatus.RUNNING.value,
    TaskStatus.WAITING_HUMAN.value,
}

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# 节点按钮可见性由阶段驱动，Client 按 process_code 取表渲染
STAGE_DEFINITIONS: dict[str, list[dict]] = {
    PROCESS_CODE_SRM_CUSTOMER_ORDER: [
        {"id": ProcessStage.CREATING_SDMS.value, "name": "建单中", "button": None},
        {"id": ProcessStage.SDMS_CREATED.value, "name": "待填写交期", "button": "填写交货日期"},
        {"id": ProcessStage.DATES_PARTIAL.value, "name": "交期填写中", "button": "填写交货日期"},
        {"id": ProcessStage.DATES_COMPLETE.value, "name": "待签章", "button": "去签章"},
        {"id": ProcessStage.SIGN_REQUESTED.value, "name": "待回签", "button": None},
        {"id": ProcessStage.SIGNED.value, "name": "已回签", "button": "手动触发签章合同下载"},
        {"id": ProcessStage.ARCHIVED.value, "name": "已完成", "button": None},
        {"id": ProcessStage.FAILED.value, "name": "失败", "button": "重试"},
    ],
    PROCESS_CODE_SRM_TIANDI_STATEMENT: [
        {
            "id": ProcessStage.STMT_GENERATING.value,
            "name": "待生成",
            "button": "重新生成",
        },
        {
            "id": ProcessStage.STMT_PENDING_INVOICE.value,
            "name": "待上传发票",
            "button": "提交审核",
        },
        {
            "id": ProcessStage.STMT_PENDING_REVIEW.value,
            "name": "提交审核",
            "button": "提交审核",
        },
        {"id": ProcessStage.STMT_SUBMITTED.value, "name": "已完成", "button": None},
        {"id": ProcessStage.STMT_CANCELLED.value, "name": "已作废", "button": None},
    ],
}


def stage_definitions_for(process_code: str) -> list[dict]:
    return STAGE_DEFINITIONS.get(process_code, [])


def _valid_date(value: str) -> bool:
    if not _DATE_PATTERN.fullmatch(value):
        return False
    try:
        return datetime.fromisoformat(value).date().isoformat() == value
    except ValueError:
        return False


async def get_instance(db: AsyncSession, tenant_id: str, instance_id: str) -> ProcessInstance:
    instance = (
        await db.execute(
            select(ProcessInstance).where(
                ProcessInstance.id == instance_id,
                ProcessInstance.tenant_id == tenant_id,
                not_deleted(ProcessInstance),
            )
        )
    ).scalar_one_or_none()
    if instance is None:
        raise NotFoundError(message="流程实例不存在", message_key="errors.autotask.process_instance_not_found")
    return instance


async def list_instances(
    db: AsyncSession,
    tenant_id: str,
    *,
    stage: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> list[ProcessInstance]:
    query = select(ProcessInstance).where(
        ProcessInstance.tenant_id == tenant_id,
        ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
        not_deleted(ProcessInstance),
    )
    if stage:
        query = query.where(ProcessInstance.stage == stage)
    if status:
        query = query.where(ProcessInstance.status == status)
    if keyword:
        query = query.where(ProcessInstance.biz_key.contains(keyword.strip()))
    result = await db.execute(query.order_by(ProcessInstance.created_at.desc()))
    return list(result.scalars().all())


async def list_line_items(db: AsyncSession, instance_id: str) -> list[ProcessLineItem]:
    result = await db.execute(
        select(ProcessLineItem)
        .where(ProcessLineItem.instance_id == instance_id, not_deleted(ProcessLineItem))
        .order_by(ProcessLineItem.line_number.asc())
    )
    return list(result.scalars().all())


async def _is_demo_portal(db: AsyncSession, portal_account_id: str | None) -> bool:
    if not portal_account_id:
        return False
    portal_url = (
        await db.execute(
            select(PortalAccount.portal_url).where(
                PortalAccount.id == portal_account_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    return _DEMO_PORTAL_HOST in str(portal_url or "")


async def list_stage_history(db: AsyncSession, instance_id: str) -> list[ProcessStageHistory]:
    result = await db.execute(
        select(ProcessStageHistory)
        .where(ProcessStageHistory.instance_id == instance_id, not_deleted(ProcessStageHistory))
        .order_by(ProcessStageHistory.created_at.asc())
    )
    return list(result.scalars().all())


async def list_sub_tasks(db: AsyncSession, instance_id: str) -> list[AutomationTask]:
    result = await db.execute(
        select(AutomationTask)
        .where(AutomationTask.process_instance_id == instance_id, not_deleted(AutomationTask))
        .order_by(AutomationTask.created_at.asc())
    )
    return list(result.scalars().all())


def to_sub_task_response(task: AutomationTask) -> "ProcessSubTaskResponse":
    from app.schemas.process import ProcessSubTaskResponse

    task_input = loads_json(task.input, {})
    line_number = str(task_input.get("line_number") or "").strip() or None
    return ProcessSubTaskResponse(
        id=task.id,
        title=task.title,
        task_type=task.task_type,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        line_number=line_number,
    )


def _change_stage(
    db: AsyncSession,
    instance: ProcessInstance,
    to_stage: ProcessStage,
    *,
    actor: str,
    note: str | None = None,
) -> None:
    if instance.stage == to_stage.value:
        return
    db.add(
        ProcessStageHistory(
            instance_id=instance.id,
            from_stage=instance.stage,
            to_stage=to_stage.value,
            actor=actor,
            note=note,
        )
    )
    instance.stage = to_stage.value


def _clear_instance_error(instance: ProcessInstance) -> None:
    instance.last_error_code = None
    instance.last_error_message = None


def _set_instance_error(
    instance: ProcessInstance,
    *,
    error_code: str | None,
    error_message: str | None,
) -> None:
    code, message = localize_process_error(error_code, error_message)
    instance.last_error_code = code
    instance.last_error_message = message


def _set_line_error(
    line: ProcessLineItem,
    *,
    error_code: str | None,
    error_message: str | None,
) -> None:
    code, message = localize_process_error(error_code, error_message)
    line.last_error_code = code
    line.last_error_message = message


def _fail_instance(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    actor: str,
    error_code: str | None,
    error_message: str | None,
) -> None:
    instance.status = ProcessInstanceStatus.FAILED.value
    _set_instance_error(instance, error_code=error_code, error_message=error_message)
    _change_stage(
        db,
        instance,
        ProcessStage.FAILED,
        actor=actor,
        note=instance.last_error_message or error_message,
    )


async def _find_binding(
    db: AsyncSession,
    tenant_id: str,
    portal_account_id: str,
    template_code: str,
) -> WorkflowBinding:
    row = (
        await db.execute(
            select(WorkflowBinding, WorkflowTemplate)
            .join(
                WorkflowTemplate,
                WorkflowTemplate.id == WorkflowBinding.workflow_template_id,
            )
            .where(
                WorkflowTemplate.tenant_id == tenant_id,
                WorkflowTemplate.code == template_code,
                not_deleted(WorkflowTemplate),
                WorkflowBinding.portal_account_id == portal_account_id,
                WorkflowBinding.status == BindingStatus.ENABLED.value,
                not_deleted(WorkflowBinding),
            )
            .order_by(WorkflowBinding.created_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        raise BadRequestError(
            message=f"未找到模板 {template_code} 在当前 Portal 的已启用 Binding",
            message_key="errors.autotask.process_binding_missing",
        )
    return row[0]


async def _create_sub_task(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    template_code: str,
    title: str,
    task_input: dict,
    actor: str,
) -> AutomationTask:
    portal = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == instance.portal_account_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if portal is None:
        raise NotFoundError(message="Portal 账号不存在", message_key="errors.autotask.portal_not_found")
    if portal.status != PortalAccountStatus.ENABLED.value:
        raise BadRequestError(
            message="门户账号未启用",
            message_key="errors.autotask.portal_disabled",
        )
    binding = await _find_binding(db, instance.tenant_id, instance.portal_account_id, template_code)
    task = AutomationTask(
        tenant_id=instance.tenant_id,
        title=title,
        task_type=template_code,
        portal_account_id=instance.portal_account_id,
        workflow_binding_id=binding.id,
        entity_type=portal.entity_type,
        erp_entity_code=portal.erp_entity_code,
        erp_entity_name=portal.erp_entity_name,
        status=TaskStatus.QUEUED,
        priority=TaskPriority.NORMAL,
        input=dumps_json(task_input),
        created_by=actor,
        assigned_to=actor,
        process_instance_id=instance.id,
    )
    db.add(task)
    await db.flush()
    db.add(
        RpaRun(
            task_id=task.id,
            rpa_flow_id=binding.rpa_flow_id,
            status=RunStatus.QUEUED,
        )
    )
    return task


async def _ensure_prepare_sub_task(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    actor: str,
    allow_missing_prepare_binding: bool = False,
) -> AutomationTask | None:
    """建单中且还没有建 SDMS 子任务时补建一条（正式演练曾缺 Binding）。"""
    if instance.status != ProcessInstanceStatus.ACTIVE.value:
        return None
    if instance.stage != ProcessStage.CREATING_SDMS.value:
        return None
    existing_task = (
        await db.execute(
            select(AutomationTask.id).where(
                AutomationTask.process_instance_id == instance.id,
                AutomationTask.task_type == CREATE_SDMS_TEMPLATE_CODE,
                not_deleted(AutomationTask),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if existing_task is not None:
        return None
    po_no = instance.biz_key
    try:
        return await _create_sub_task(
            db,
            instance,
            template_code=CREATE_SDMS_TEMPLATE_CODE,
            title=f"1. 建 SDMS 销售订单 - {po_no}",
            task_input={"po_no": po_no},
            actor=actor,
        )
    except BadRequestError as exc:
        if not allow_missing_prepare_binding or exc.message_key != "errors.autotask.process_binding_missing":
            raise
        return None


async def create_from_scan(
    db: AsyncSession,
    tenant_id: str,
    portal_account_id: str,
    orders: list[dict],
    *,
    actor: str,
    commit: bool = True,
    allow_missing_prepare_binding: bool = False,
) -> list[ProcessInstance]:
    """扫单结果幂等创建主任务；已存在 (portal, process_code, po_no) 直接跳过。"""
    portal = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == portal_account_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    customer_label = (portal.portal_name.strip() if portal and portal.portal_name else "客户").strip() or "客户"
    created: list[ProcessInstance] = []
    for order in orders:
        po_no = str(order.get("poNo") or order.get("po_no") or "").strip().upper()
        if not po_no:
            continue
        existing = (
            await db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.portal_account_id == portal_account_id,
                    ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
                    ProcessInstance.biz_key == po_no,
                    not_deleted(ProcessInstance),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            await _ensure_prepare_sub_task(
                db,
                existing,
                actor=actor,
                allow_missing_prepare_binding=allow_missing_prepare_binding,
            )
            continue
        instance = ProcessInstance(
            tenant_id=tenant_id,
            process_code=PROCESS_CODE_SRM_CUSTOMER_ORDER,
            biz_key=po_no,
            title=f"{customer_label}·客户订单 - {po_no}",
            portal_account_id=portal_account_id,
            stage=ProcessStage.CREATING_SDMS.value,
            status=ProcessInstanceStatus.ACTIVE.value,
            summary=dumps_json({"poNo": po_no}),
            created_by=actor,
        )
        db.add(instance)
        await db.flush()
        db.add(
            ProcessStageHistory(
                instance_id=instance.id,
                from_stage=None,
                to_stage=ProcessStage.CREATING_SDMS.value,
                actor=actor,
                note="扫单发现待签章订单",
            )
        )
        try:
            await _create_sub_task(
                db,
                instance,
                template_code=CREATE_SDMS_TEMPLATE_CODE,
                title=f"1. 建 SDMS 销售订单 - {po_no}",
                task_input={"po_no": po_no},
                actor=actor,
            )
        except BadRequestError as exc:
            if not allow_missing_prepare_binding or exc.message_key != "errors.autotask.process_binding_missing":
                raise
        created.append(instance)
    if commit:
        await db.commit()
    return created


async def submit_line_date(
    db: AsyncSession,
    tenant_id: str,
    instance_id: str,
    line_number: str,
    expected_date: str,
    user: UserCache,
) -> ProcessLineItem:
    instance = await get_instance(db, tenant_id, instance_id)
    if instance.status != ProcessInstanceStatus.ACTIVE.value or instance.stage not in {
        ProcessStage.SDMS_CREATED.value,
        ProcessStage.DATES_PARTIAL.value,
    }:
        raise BadRequestError(
            message="当前阶段不允许填写交货日期",
            message_key="errors.autotask.process_stage_not_editable",
        )
    if not _valid_date(expected_date):
        raise BadRequestError(
            message="预计交货日期必须为 YYYY-MM-DD",
            message_key="errors.autotask.process_line_date_invalid",
        )
    line = (
        await db.execute(
            select(ProcessLineItem).where(
                ProcessLineItem.instance_id == instance.id,
                ProcessLineItem.line_number == line_number,
                not_deleted(ProcessLineItem),
            )
        )
    ).scalar_one_or_none()
    if line is None:
        raise NotFoundError(message="订单行不存在", message_key="errors.autotask.process_line_not_found")
    if line.line_status == ProcessLineStatus.SUBMITTING.value:
        raise BadRequestError(
            message="该行正在写入中，请稍候",
            message_key="errors.autotask.process_line_submitting",
        )
    if line.line_status == ProcessLineStatus.WRITTEN.value and line.expected_delivery_date == expected_date:
        return line

    line.expected_delivery_date = expected_date
    line.line_status = ProcessLineStatus.SUBMITTING.value
    line.last_error_code = None
    line.last_error_message = None
    task = await _create_sub_task(
        db,
        instance,
        template_code=FILL_LINE_DATE_TEMPLATE_CODE,
        title=f"2. 填写交货日期(行{line_number}) - {instance.biz_key}",
        task_input={
            "po_no": instance.biz_key,
            "line_number": line_number,
            "expected_delivery_date": expected_date,
        },
        actor=user.user_id,
    )
    line.sub_task_id = task.id
    if instance.stage == ProcessStage.SDMS_CREATED.value:
        _change_stage(db, instance, ProcessStage.DATES_PARTIAL, actor=user.user_id)
    await db.commit()
    await db.refresh(line)
    return line


async def request_sign(db: AsyncSession, tenant_id: str, instance_id: str, user: UserCache) -> ProcessInstance:
    instance = await get_instance(db, tenant_id, instance_id)
    if instance.status != ProcessInstanceStatus.ACTIVE.value or instance.stage != ProcessStage.DATES_COMPLETE.value:
        raise BadRequestError(
            message="全部行交期写入完成后才能发起签章",
            message_key="errors.autotask.process_sign_not_ready",
        )
    # TEMP_E2E_ONLY: 演示门户不落库时，把 AutoTask 已写交期传给签章 Flow 做签章前回填。
    # 只给演示站。正式站没有交期框/签章，不得回填。门户保存持久化后删除本段。
    lines = await list_line_items(db, instance.id)
    written_lines = [
        {
            "line_number": item.line_number,
            "expected_delivery_date": item.expected_delivery_date,
        }
        for item in lines
        if item.line_status == ProcessLineStatus.WRITTEN.value and item.expected_delivery_date
    ]
    task_input: dict = {"po_no": instance.biz_key}
    if written_lines and await _is_demo_portal(db, instance.portal_account_id):
        task_input["temp_e2e_backfill_dates"] = True
        task_input["order_lines"] = written_lines
    await _create_sub_task(
        db,
        instance,
        template_code=SIGN_TEMPLATE_CODE,
        title=f"3. 发起签章 - {instance.biz_key}",
        task_input=task_input,
        actor=user.user_id,
    )
    await db.commit()
    await db.refresh(instance)
    return instance


async def archive_signed_order(
    db: AsyncSession,
    tenant_id: str,
    instance_id: str,
    user: UserCache,
    *,
    sdms_username: str = "",
) -> ProcessInstance:
    """手动兜底：仅在已确认已回签（SIGNED）后可触发合同下载上传。

    待回签阶段双方可能仍在盖章（客户→我司），此时下载上传无业务意义。
    轮询确认已回签后阶段先变为已回签；若自动下载上传失败，可在此重试。
    """
    instance = await get_instance(db, tenant_id, instance_id)
    if instance.status != ProcessInstanceStatus.ACTIVE.value or instance.stage != ProcessStage.SIGNED.value:
        raise BadRequestError(
            message="仅在已回签阶段可手动触发签章合同下载",
            message_key="errors.autotask.process_archive_not_ready",
        )
    raw_name = getattr(user, "name", "")
    username = str(sdms_username or "").strip() or (
        raw_name.strip() if isinstance(raw_name, str) else ""
    )
    if not username:
        raise BadRequestError(
            message="缺少当前登录工号，无法上传签章合同到 SDMS",
            message_key="errors.autotask.sdms_username_missing",
        )
    await _trigger_archive_if_needed(
        db,
        instance,
        actor=user.user_id,
        note="客服手动确认 SRM 已回签并触发归档",
        sdms_username=username,
    )
    await db.commit()
    await db.refresh(instance)
    return instance


async def _list_instance_tasks_by_type(
    db: AsyncSession,
    instance_id: str,
    template_code: str,
) -> list[AutomationTask]:
    result = await db.execute(
        select(AutomationTask).where(
            AutomationTask.process_instance_id == instance_id,
            AutomationTask.task_type == template_code,
            not_deleted(AutomationTask),
        )
    )
    return list(result.scalars().all())


async def _has_archive_in_progress_or_success(db: AsyncSession, instance_id: str) -> bool:
    tasks = await _list_instance_tasks_by_type(db, instance_id, ARCHIVE_TEMPLATE_CODE)
    return any(task.status in _ARCHIVE_SKIP_STATUSES for task in tasks)


async def _has_check_reply_in_flight(db: AsyncSession, instance_id: str) -> bool:
    tasks = await _list_instance_tasks_by_type(db, instance_id, CHECK_REPLY_TEMPLATE_CODE)
    return any(task.status in _CHECK_REPLY_IN_FLIGHT for task in tasks)


def _summary_sdms_username(instance: ProcessInstance) -> str:
    summary = loads_json(instance.summary, {})
    if not isinstance(summary, dict):
        return ""
    return str(summary.get("sdmsUsername") or "").strip()


def _store_sdms_username(instance: ProcessInstance, username: str) -> None:
    summary = loads_json(instance.summary, {})
    if not isinstance(summary, dict):
        summary = {}
    summary["sdmsUsername"] = username
    instance.summary = dumps_json(summary)


async def _resolve_archive_username(
    db: AsyncSession,
    instance: ProcessInstance,
    sdms_username: str,
) -> str:
    username = str(sdms_username or "").strip() or _summary_sdms_username(instance)
    if username:
        return username
    username = await username_from_user_cache(db, instance.created_by)
    if username:
        return username
    return _FALLBACK_ARCHIVE_SDMS_USERNAME


async def _trigger_archive_if_needed(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    actor: str,
    note: str,
    sdms_username: str = "",
) -> bool:
    """确认已回签后：先推进到 SIGNED（已回签），再幂等创建归档子任务。

    阶段先变、下载后发：即使归档任务创建失败/已存在，实例也停在已回签，
    客服可用「手动触发签章合同下载」重试。
    """
    if instance.status != ProcessInstanceStatus.ACTIVE.value or instance.stage not in {
        ProcessStage.DATES_COMPLETE.value,
        ProcessStage.SIGN_REQUESTED.value,
        ProcessStage.SIGNED.value,
    }:
        return False
    if instance.stage in {
        ProcessStage.DATES_COMPLETE.value,
        ProcessStage.SIGN_REQUESTED.value,
    }:
        _change_stage(db, instance, ProcessStage.SIGNED, actor=actor, note=note)
    if await _has_archive_in_progress_or_success(db, instance.id):
        return False
    username = await _resolve_archive_username(db, instance, sdms_username)
    if not username:
        _set_instance_error(
            instance,
            error_code="SDMS_USERNAME_MISSING",
            error_message="缺少 Auth 登录工号，无法上传签章合同到 SDMS",
        )
        return False
    _store_sdms_username(instance, username)
    await _create_sub_task(
        db,
        instance,
        template_code=ARCHIVE_TEMPLATE_CODE,
        title=f"4. 双方签章合同下载上传 - {instance.biz_key}",
        task_input={"po_no": instance.biz_key, "username": username},
        actor=actor,
    )
    return True


async def create_check_reply_task(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    actor: str,
) -> AutomationTask | None:
    """为待回签/待签章实例创建回签探测子任务；已有进行中探测则跳过。

    待签章（DATES_COMPLETE）纳入探测是演示门户 TEMP：SRM 种子「已回签」单
    可在未走过签章节点时被轮询发现并归档。
    """
    if instance.status != ProcessInstanceStatus.ACTIVE.value:
        return None
    if instance.stage not in {
        ProcessStage.DATES_COMPLETE.value,
        ProcessStage.SIGN_REQUESTED.value,
    }:
        return None
    if await _has_check_reply_in_flight(db, instance.id):
        return None
    if await _has_archive_in_progress_or_success(db, instance.id):
        return None
    return await _create_sub_task(
        db,
        instance,
        template_code=CHECK_REPLY_TEMPLATE_CODE,
        title=f"回签探测 - {instance.biz_key}",
        task_input={"po_no": instance.biz_key},
        actor=actor,
    )


async def list_sign_poll_candidates(db: AsyncSession) -> list[ProcessInstance]:
    """回签轮询候选：ACTIVE 且阶段为待回签或待签章，且门户仍启用。"""
    result = await db.execute(
        select(ProcessInstance)
        .join(PortalAccount, PortalAccount.id == ProcessInstance.portal_account_id)
        .where(
            ProcessInstance.process_code == PROCESS_CODE_SRM_CUSTOMER_ORDER,
            ProcessInstance.status == ProcessInstanceStatus.ACTIVE.value,
            or_(
                ProcessInstance.stage == ProcessStage.SIGN_REQUESTED.value,
                ProcessInstance.stage == ProcessStage.DATES_COMPLETE.value,
            ),
            PortalAccount.status == PortalAccountStatus.ENABLED.value,
            not_deleted(ProcessInstance),
            not_deleted(PortalAccount),
        )
    )
    return list(result.scalars().all())


async def list_sign_requested_instances(db: AsyncSession) -> list[ProcessInstance]:
    """兼容旧名：等同 list_sign_poll_candidates。"""
    return await list_sign_poll_candidates(db)


async def run_sign_poll_once(db: AsyncSession, *, actor: str) -> dict[str, int]:
    """立即跑一轮回签探测（列表按钮 / 可被调度器复用创建逻辑）。

    返回 candidate_count / created_count。逐条 commit，单条失败不影响其它。
    """
    instances = await list_sign_poll_candidates(db)
    created = 0
    for instance in instances:
        try:
            task = await create_check_reply_task(db, instance, actor=actor)
            if task is not None:
                await db.commit()
                created += 1
            else:
                await db.rollback()
        except Exception:
            await db.rollback()
            # 与 SignPollScheduler 一致：单条失败继续下一条
            continue
    return {"candidate_count": len(instances), "created_count": created}

async def cancel_instance(db: AsyncSession, tenant_id: str, instance_id: str, user: UserCache) -> ProcessInstance:
    instance = await get_instance(db, tenant_id, instance_id)
    if instance.status in {ProcessInstanceStatus.COMPLETED.value, ProcessInstanceStatus.CANCELLED.value}:
        raise BadRequestError(
            message="流程已结束，不允许取消",
            message_key="errors.autotask.process_cancel_not_allowed",
        )
    instance.status = ProcessInstanceStatus.CANCELLED.value
    _change_stage(db, instance, ProcessStage.FAILED, actor=user.user_id, note="人工取消")
    await db.commit()
    await db.refresh(instance)
    return instance


async def retry_instance(db: AsyncSession, tenant_id: str, instance_id: str, user: UserCache) -> ProcessInstance:
    """失败重试：按失败前节点重新触发对应子任务。"""
    instance = await get_instance(db, tenant_id, instance_id)
    if instance.status != ProcessInstanceStatus.FAILED.value:
        raise BadRequestError(
            message="仅失败的流程实例可重试",
            message_key="errors.autotask.process_retry_not_allowed",
        )
    instance.status = ProcessInstanceStatus.ACTIVE.value
    _clear_instance_error(instance)
    if instance.line_total == 0:
        _change_stage(db, instance, ProcessStage.CREATING_SDMS, actor=user.user_id, note="重试建单")
        await _create_sub_task(
            db,
            instance,
            template_code=CREATE_SDMS_TEMPLATE_CODE,
            title=f"1. 建 SDMS 销售订单 - {instance.biz_key}",
            task_input={"po_no": instance.biz_key},
            actor=user.user_id,
        )
    else:
        _change_stage(db, instance, ProcessStage.SDMS_CREATED, actor=user.user_id, note="重试后回到待填写交货日期")
    await db.commit()
    await db.refresh(instance)
    return instance


async def on_sub_task_finished(db: AsyncSession, task: AutomationTask, run: RpaRun) -> None:
    """finish_run 钩子：子任务终态推进流程实例。调用方负责整体事务。"""
    from app.services import statement_service

    if await statement_service.dispatch_statement_finished(db, task, run):
        return
    if task.task_type == SCAN_TASK_TYPE:
        if run.status == RunStatus.SUCCESS.value:
            await _handle_scan_success(db, task, run)
        return
    if not task.process_instance_id:
        return
    instance = (
        await db.execute(
            select(ProcessInstance)
            .where(ProcessInstance.id == task.process_instance_id, not_deleted(ProcessInstance))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if instance is None:
        return

    succeeded = run.status == RunStatus.SUCCESS.value
    if task.task_type == CREATE_SDMS_TEMPLATE_CODE:
        await _handle_create_sdms_finished(db, instance, run, succeeded)
    elif task.task_type == FILL_LINE_DATE_TEMPLATE_CODE:
        await _handle_fill_line_finished(db, instance, task, run, succeeded)
    elif task.task_type == SIGN_TEMPLATE_CODE:
        await _handle_sign_finished(db, instance, run, succeeded)
    elif task.task_type == CHECK_REPLY_TEMPLATE_CODE:
        await _handle_check_reply_finished(db, instance, run, succeeded)
    elif task.task_type == ARCHIVE_TEMPLATE_CODE:
        await _handle_archive_finished(db, instance, run, succeeded)


async def _handle_scan_success(db: AsyncSession, task: AutomationTask, run: RpaRun) -> None:
    output = run.output if isinstance(run.output, dict) else {}
    if output.get("schemaVersion") != SCAN_OUTPUT_SCHEMA:
        return
    orders = output.get("orders")
    if not isinstance(orders, list) or not orders:
        return
    drill = output.get("drill") if isinstance(output.get("drill"), dict) else {}
    assumed = bool(drill.get("assumedPending"))
    created = await create_from_scan(
        db,
        task.tenant_id,
        task.portal_account_id,
        orders,
        actor=task.created_by,
        commit=False,
        allow_missing_prepare_binding=assumed,
    )
    if assumed:
        for instance in created:
            _mark_assumed_pending_drill(instance, instance.biz_key)


def _mark_assumed_pending_drill(instance: ProcessInstance, po_no: str) -> None:
    summary = loads_json(instance.summary, {})
    if not isinstance(summary, dict):
        summary = {}
    summary["poNo"] = po_no
    summary["drill"] = {
        "uncommitted": False,
        "shadow": True,
        "assumedPending": True,
        "step": "srm.scan_pending_orders",
        "blockedAction": None,
        "at": datetime.now(UTC).isoformat(),
        "note": "正式站无待签章，演练按订单编号导出后当成待签章扫入",
    }
    instance.summary = dumps_json(summary)


async def _handle_create_sdms_finished(
    db: AsyncSession,
    instance: ProcessInstance,
    run: RpaRun,
    succeeded: bool,
) -> None:
    if not succeeded:
        _fail_instance(
            db,
            instance,
            actor="system",
            error_code=run.error_code,
            error_message=run.error_message or "建 SDMS 销售订单失败",
        )
        return
    output = run.output if isinstance(run.output, dict) else {}
    raw_lines = output.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        _fail_instance(
            db,
            instance,
            actor="system",
            error_code="PROCESS_OUTPUT_LINES_MISSING",
            error_message="建单子任务成功输出缺少订单行",
        )
        return
    for raw_line in raw_lines:
        if not isinstance(raw_line, dict):
            continue
        line_number = _optional_str(raw_line.get("lineNumber")) or ""
        material_number = _optional_str(raw_line.get("customerItemNumber")) or ""
        if not line_number or not material_number:
            continue
        db.add(
            ProcessLineItem(
                instance_id=instance.id,
                line_number=line_number,
                material_number=material_number,
                item_name=_optional_str(raw_line.get("itemName")),
                item_specification=_optional_str(raw_line.get("itemSpecification")),
                material_status=_optional_str(raw_line.get("materialStatus")),
                internal_code=_optional_str(raw_line.get("internalCode")),
                order_quantity=_optional_str(raw_line.get("orderQuantity")),
                order_quantity_uom=_optional_str(raw_line.get("orderQuantityUom")),
                unit_selling_price=_optional_str(raw_line.get("unitSellingPrice")),
                tax_included_amount=_optional_str(raw_line.get("taxIncludedAmount")),
                request_date=_optional_str(raw_line.get("requestDate")),
                standard_delivery_days=_optional_str(raw_line.get("standardDeliveryDays")),
                meets_lead_time=_optional_str(raw_line.get("meetsLeadTime")),
                supplier_delivery_date=_optional_str(raw_line.get("supplierDeliveryDate")),
                outstanding_quantity=_optional_str(raw_line.get("outstandingQuantity")),
                remarks=_optional_str(raw_line.get("remarks")),
                direct_shipment_remarks=_optional_str(raw_line.get("directShipmentRemarks")),
                line_status=ProcessLineStatus.PENDING.value,
            )
        )
    await db.flush()
    instance.line_total = len(await list_line_items(db, instance.id))
    instance.line_done = 0
    existing = loads_json(instance.summary, {})
    if not isinstance(existing, dict):
        existing = {}
    instance.summary = dumps_json(
        {
            "poNo": output.get("poNo"),
            "orderNumber": output.get("orderNumber"),
            "headerId": output.get("headerId"),
            "supplierCode": output.get("supplierCode"),
            "supplierName": output.get("supplierName"),
            "sdmsUsername": existing.get("sdmsUsername"),
        }
    )
    _clear_instance_error(instance)
    _change_stage(db, instance, ProcessStage.SDMS_CREATED, actor="system", note="SDMS 销售订单已创建")


async def _handle_fill_line_finished(
    db: AsyncSession,
    instance: ProcessInstance,
    task: AutomationTask,
    run: RpaRun,
    succeeded: bool,
) -> None:
    task_input = loads_json(task.input, {})
    line_number = str(task_input.get("line_number") or "").strip()
    line = (
        await db.execute(
            select(ProcessLineItem).where(
                ProcessLineItem.instance_id == instance.id,
                ProcessLineItem.line_number == line_number,
                not_deleted(ProcessLineItem),
            )
        )
    ).scalar_one_or_none()
    if line is None:
        return
    if succeeded:
        line.line_status = ProcessLineStatus.WRITTEN.value
        line.last_error_code = None
        line.last_error_message = None
    else:
        # 子任务失败不回滚：仅标记该行失败，等待人工重试
        line.line_status = ProcessLineStatus.WRITE_FAILED.value
        _set_line_error(line, error_code=run.error_code, error_message=run.error_message)
    await db.flush()
    lines = await list_line_items(db, instance.id)
    instance.line_total = len(lines)
    instance.line_done = sum(1 for item in lines if item.line_status == ProcessLineStatus.WRITTEN.value)
    if instance.line_total > 0 and instance.line_done == instance.line_total:
        _clear_instance_error(instance)
        _change_stage(db, instance, ProcessStage.DATES_COMPLETE, actor="system", note="全部行交期已写入")
    elif instance.stage != ProcessStage.DATES_PARTIAL.value:
        _change_stage(db, instance, ProcessStage.DATES_PARTIAL, actor="system")


async def _handle_sign_finished(
    db: AsyncSession,
    instance: ProcessInstance,
    run: RpaRun,
    succeeded: bool,
) -> None:
    if succeeded:
        # 签章成功后清除历史失败文案，避免「已待回签/已完成」仍显示旧错误误导客服。
        # 正式路径：一律停在 SIGN_REQUESTED，由 30 分钟回签轮询（或人工兜底）再归档。
        # 演示门户签章瞬间常闪「已回签」但不落库，不可据此立即触发节点4。
        _clear_instance_error(instance)
        _change_stage(db, instance, ProcessStage.SIGN_REQUESTED, actor="system", note="SRM 已发起签章，待双方签章")
    else:
        _set_instance_error(
            instance,
            error_code=run.error_code,
            error_message=run.error_message,
        )


async def _handle_check_reply_finished(
    db: AsyncSession,
    instance: ProcessInstance,
    run: RpaRun,
    succeeded: bool,
) -> None:
    if not succeeded:
        _set_instance_error(
            instance,
            error_code=run.error_code,
            error_message=run.error_message,
        )
        return
    output = run.output if isinstance(run.output, dict) else {}
    reply_status = _optional_str(output.get("replyStatus"))
    if reply_status == SIGNED_REPLY_STATUS:
        _clear_instance_error(instance)
        username = await _resolve_archive_username(db, instance, "")
        await _trigger_archive_if_needed(
            db,
            instance,
            actor="sign-poll-scheduler",
            note="轮询发现 SRM 已回签，自动归档",
            sdms_username=username,
        )


async def _handle_archive_finished(
    db: AsyncSession,
    instance: ProcessInstance,
    run: RpaRun,
    succeeded: bool,
) -> None:
    if succeeded:
        _clear_instance_error(instance)
        _change_stage(db, instance, ProcessStage.ARCHIVED, actor="system", note="双方签章合同已上传 SDMS")
        instance.status = ProcessInstanceStatus.COMPLETED.value
    else:
        _set_instance_error(
            instance,
            error_code=run.error_code,
            error_message=run.error_message,
        )


async def create_scan_task(
    db: AsyncSession,
    tenant_id: str,
    portal_account_id: str,
    *,
    actor: str,
) -> AutomationTask:
    """创建扫单子任务（用户不可见），由调度器或手动 API 触发。"""
    portal = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == portal_account_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if portal is None:
        raise NotFoundError(message="Portal 账号不存在", message_key="errors.autotask.portal_not_found")
    if portal.status != PortalAccountStatus.ENABLED.value:
        raise BadRequestError(
            message="门户账号未启用",
            message_key="errors.autotask.portal_disabled",
        )
    binding = await _find_binding(db, tenant_id, portal_account_id, SCAN_TASK_TYPE)
    task = AutomationTask(
        tenant_id=tenant_id,
        title="扫单：SRM 待签章订单",
        task_type=SCAN_TASK_TYPE,
        portal_account_id=portal_account_id,
        workflow_binding_id=binding.id,
        entity_type=portal.entity_type,
        erp_entity_code=portal.erp_entity_code,
        erp_entity_name=portal.erp_entity_name,
        status=TaskStatus.QUEUED,
        priority=TaskPriority.LOW,
        input=dumps_json({}),
        created_by=actor,
        assigned_to=actor,
    )
    db.add(task)
    await db.flush()
    db.add(
        RpaRun(
            task_id=task.id,
            rpa_flow_id=binding.rpa_flow_id,
            status=RunStatus.QUEUED,
        )
    )
    await db.commit()
    await db.refresh(task)
    return task
