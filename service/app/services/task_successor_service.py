"""任务成功后的后继任务配置、映射和可靠创建。"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import (
    BindingStatus,
    RunStatus,
    SuccessorJobStatus,
    TaskStatus,
)
from app.models.portal_account import PortalAccount
from app.models.rpa_run import RpaRun
from app.models.task_message import TaskMessage
from app.models.task_successor_job import TaskSuccessorJob
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json, loads_json

logger = logging.getLogger(__name__)

SUCCESSOR_INPUT_MAPPER = "ORDER_DELIVERY_CONFIRMATION_V1"
ATTACHMENT_UPLOAD_INPUT_MAPPER = "ORDER_ATTACHMENT_UPLOAD_V1"
SOURCE_OUTPUT_SCHEMA = "ORDER_DOWNLOAD_PUSH_OUTPUT_V1"
ATTACHMENT_SOURCE_OUTPUT_SCHEMA = "ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1"
TARGET_WORKFLOW_CODE = "srm_update_expected_delivery_dates"
ATTACHMENT_TARGET_WORKFLOW_CODE = "srm_upload_order_attachment"
_SUPPORTED_SUCCESSORS = {
    SUCCESSOR_INPUT_MAPPER: (SOURCE_OUTPUT_SCHEMA, TARGET_WORKFLOW_CODE),
    ATTACHMENT_UPLOAD_INPUT_MAPPER: (
        ATTACHMENT_SOURCE_OUTPUT_SCHEMA,
        ATTACHMENT_TARGET_WORKFLOW_CODE,
    ),
}
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RETRY_DELAYS_SECONDS = (5, 30, 120, 600, 1800, 3600)


class SuccessorJobError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable


def _successor_spec(config: Mapping[str, Any]) -> tuple[str, str] | None:
    raw = config.get("successor")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("successor must be an object")
    if raw.get("on") != "SUCCESS":
        raise ValueError("successor.on must be SUCCESS")
    target_binding_id = raw.get("targetWorkflowBindingId")
    input_mapper = raw.get("inputMapper")
    if not isinstance(target_binding_id, str) or not target_binding_id.strip():
        raise ValueError("successor.targetWorkflowBindingId is required")
    if not isinstance(input_mapper, str) or input_mapper not in _SUPPORTED_SUCCESSORS:
        raise ValueError(f"successor.inputMapper must be one of {', '.join(sorted(_SUPPORTED_SUCCESSORS))}")
    return target_binding_id.strip(), input_mapper


async def validate_successor_binding_config(
    db: AsyncSession,
    *,
    tenant_id: str,
    source_portal_account_id: str,
    config: Mapping[str, Any],
    source_binding_id: str | None = None,
) -> None:
    try:
        spec = _successor_spec(config)
    except ValueError as exc:
        raise BadRequestError(
            message=str(exc),
            message_key="errors.autotask.successor_config_invalid",
        ) from exc
    if spec is None:
        return
    target_binding_id, input_mapper = spec
    if source_binding_id is not None and target_binding_id == source_binding_id:
        raise BadRequestError(
            message="后继 Binding 不能指向自身",
            message_key="errors.autotask.successor_binding_self_reference",
        )

    row = (
        await db.execute(
            select(WorkflowBinding, PortalAccount, WorkflowTemplate)
            .join(PortalAccount, WorkflowBinding.portal_account_id == PortalAccount.id)
            .join(
                WorkflowTemplate,
                WorkflowBinding.workflow_template_id == WorkflowTemplate.id,
            )
            .where(
                WorkflowBinding.id == target_binding_id,
                PortalAccount.tenant_id == tenant_id,
                WorkflowTemplate.tenant_id == tenant_id,
                not_deleted(WorkflowBinding),
                not_deleted(PortalAccount),
                not_deleted(WorkflowTemplate),
            )
        )
    ).one_or_none()
    if row is None:
        raise BadRequestError(
            message="后继 Workflow Binding 不存在",
            message_key="errors.autotask.successor_binding_not_found",
        )
    target, _, template = row
    if target.status != BindingStatus.ENABLED:
        raise BadRequestError(
            message="后继 Workflow Binding 未启用",
            message_key="errors.autotask.successor_binding_disabled",
        )
    if target.portal_account_id != source_portal_account_id:
        raise BadRequestError(
            message="来源和后继 Binding 必须使用同一个 Portal",
            message_key="errors.autotask.successor_portal_mismatch",
        )
    if not target.rpa_flow_version_id or not target.flow_checksum_snapshot:
        raise BadRequestError(
            message="后继 Binding 缺少精确 Flow 版本快照",
            message_key="errors.autotask.successor_flow_snapshot_missing",
        )
    target_workflow_code = _SUPPORTED_SUCCESSORS[input_mapper][1]
    if template.code != target_workflow_code:
        raise BadRequestError(
            message=f"后继模板必须为 {target_workflow_code}",
            message_key="errors.autotask.successor_workflow_code_invalid",
        )


async def enqueue_successor_job(
    db: AsyncSession,
    *,
    source_task: AutomationTask,
    source_run: RpaRun,
    source_binding: WorkflowBinding,
) -> TaskSuccessorJob | None:
    config = loads_json(source_binding.config, {})
    try:
        spec = _successor_spec(config)
    except ValueError as exc:
        logger.error(
            "来源 Binding 的后继配置无效",
            extra={"taskId": source_task.id, "runId": source_run.id},
        )
        db.add(
            TaskMessage(
                task_id=source_task.id,
                role="system",
                content=f"后继任务配置无效，未创建后继作业：{exc}",
                created_by=source_task.created_by,
            )
        )
        return None
    if spec is None:
        return None
    target_binding_id, input_mapper = spec

    existing = (
        await db.execute(
            select(TaskSuccessorJob).where(
                TaskSuccessorJob.source_run_id == source_run.id,
                TaskSuccessorJob.target_workflow_binding_id == target_binding_id,
                not_deleted(TaskSuccessorJob),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    job = TaskSuccessorJob(
        tenant_id=source_task.tenant_id,
        source_task_id=source_task.id,
        source_run_id=source_run.id,
        target_workflow_binding_id=target_binding_id,
        input_mapper=input_mapper,
        status=SuccessorJobStatus.PENDING,
        attempt_count=0,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(job)
    return job


def validate_delivery_confirmation_input(input_data: Mapping[str, Any]) -> None:
    order_lines = input_data.get("order_lines")
    if not isinstance(order_lines, list) or not order_lines:
        raise BadRequestError(
            message="交货日期任务必须包含非空 order_lines",
            message_key="errors.autotask.delivery_lines_required",
        )
    seen_line_numbers: set[str] = set()
    invalid_fields: list[str] = []
    for index, raw_line in enumerate(order_lines):
        if not isinstance(raw_line, Mapping):
            invalid_fields.append(f"order_lines[{index}]")
            continue
        line_number = raw_line.get("line_number")
        material_number = raw_line.get("material_number")
        expected_date = raw_line.get("expected_delivery_date")
        if not isinstance(line_number, str) or not line_number.strip():
            invalid_fields.append(f"order_lines[{index}].line_number")
        elif line_number in seen_line_numbers:
            invalid_fields.append(f"order_lines[{index}].line_number")
        else:
            seen_line_numbers.add(line_number)
        if not isinstance(material_number, str) or not material_number.strip():
            invalid_fields.append(f"order_lines[{index}].material_number")
        if not isinstance(expected_date, str) or not _valid_date(expected_date):
            invalid_fields.append(f"order_lines[{index}].expected_delivery_date")
    if invalid_fields:
        raise BadRequestError(
            message="交货日期任务输入不完整或格式错误",
            message_key="errors.autotask.delivery_input_invalid",
            details={"fields": invalid_fields},
        )


def _valid_date(value: str) -> bool:
    if _DATE_PATTERN.fullmatch(value) is None:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_INVALID",
            f"来源输出缺少有效字段 {field}",
        )
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def map_delivery_confirmation_input(
    output: Mapping[str, Any] | None,
    *,
    source_task_id: str,
    source_run_id: str,
) -> dict[str, Any]:
    if not isinstance(output, Mapping):
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_MISSING",
            "来源 Run 没有结构化成功输出",
        )
    if output.get("schemaVersion") != SOURCE_OUTPUT_SCHEMA:
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_SCHEMA_UNSUPPORTED",
            "来源 Run 输出 Schema 不受支持",
        )
    po_no = _required_text(output.get("poNo"), "poNo")
    order_number = _required_text(output.get("orderNumber"), "orderNumber")
    supplier_code = _required_text(output.get("supplierCode"), "supplierCode")
    supplier_name = _required_text(output.get("supplierName"), "supplierName")
    raw_lines = output.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_LINES_MISSING",
            "来源 Run 输出没有订单行",
        )
    line_count = output.get("lineCount")
    if not isinstance(line_count, int) or isinstance(line_count, bool):
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_LINE_COUNT_INVALID",
            "来源 Run 输出的 lineCount 无效",
        )
    if line_count != len(raw_lines):
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_LINE_COUNT_MISMATCH",
            "来源 Run 输出的订单行数量不一致",
        )

    seen: set[str] = set()
    order_lines: list[dict[str, Any]] = []
    for index, raw_line in enumerate(raw_lines):
        if not isinstance(raw_line, Mapping):
            raise SuccessorJobError(
                "SUCCESSOR_OUTPUT_LINE_INVALID",
                f"来源输出第 {index + 1} 行不是对象",
            )
        line_number = _required_text(raw_line.get("lineNumber"), "lineNumber")
        material_number = _required_text(
            raw_line.get("customerItemNumber"),
            "customerItemNumber",
        )
        if line_number in seen:
            raise SuccessorJobError(
                "SUCCESSOR_OUTPUT_LINE_DUPLICATE",
                f"来源输出包含重复行号 {line_number}",
            )
        seen.add(line_number)
        order_lines.append(
            {
                "line_number": line_number,
                "material_number": material_number,
                "item_name": _optional_text(raw_line.get("itemName")),
                "item_specification": _optional_text(raw_line.get("itemSpecification")),
                "order_quantity": _optional_text(raw_line.get("orderQuantity")),
                "order_quantity_uom": _optional_text(raw_line.get("orderQuantityUom")),
                "request_date": _optional_text(raw_line.get("requestDate")),
                "standard_delivery_days": _optional_text(raw_line.get("standardDeliveryDays")),
                "expected_delivery_date": None,
            }
        )
    return {
        "po_no": po_no,
        "order_number": order_number,
        "supplier_code": supplier_code,
        "supplier_name": supplier_name,
        "source_task_id": source_task_id,
        "source_run_id": source_run_id,
        "order_lines": order_lines,
    }


def map_attachment_upload_input(
    output: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(output, Mapping):
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_MISSING",
            "来源 Run 没有结构化成功输出",
        )
    if output.get("schemaVersion") != ATTACHMENT_SOURCE_OUTPUT_SCHEMA:
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_SCHEMA_UNSUPPORTED",
            "来源 Run 输出 Schema 不受支持",
        )
    if output.get("signed") is not True:
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_NOT_SIGNED",
            "来源 Run 未确认订单已经签章",
        )
    reply_status = _required_text(output.get("replyStatus"), "replyStatus")
    if reply_status != "已回签":
        raise SuccessorJobError(
            "SUCCESSOR_OUTPUT_REPLY_STATUS_INVALID",
            "来源 Run 的订单回复状态不是已回签",
        )
    return {"po_no": _required_text(output.get("poNo"), "poNo")}


async def list_successor_jobs(
    db: AsyncSession,
    *,
    tenant_id: str,
    source_task_id: str,
) -> list[TaskSuccessorJob]:
    result = await db.execute(
        select(TaskSuccessorJob)
        .where(
            TaskSuccessorJob.tenant_id == tenant_id,
            TaskSuccessorJob.source_task_id == source_task_id,
            not_deleted(TaskSuccessorJob),
        )
        .order_by(TaskSuccessorJob.created_at.asc())
    )
    return list(result.scalars().all())


async def retry_successor_job(
    db: AsyncSession,
    *,
    tenant_id: str,
    source_task_id: str,
    job_id: str,
) -> TaskSuccessorJob:
    job = (
        await db.execute(
            select(TaskSuccessorJob)
            .where(
                TaskSuccessorJob.id == job_id,
                TaskSuccessorJob.tenant_id == tenant_id,
                TaskSuccessorJob.source_task_id == source_task_id,
                not_deleted(TaskSuccessorJob),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError(
            message="后继任务作业不存在",
            message_key="errors.autotask.successor_job_not_found",
        )
    if job.status != SuccessorJobStatus.FAILED:
        raise BadRequestError(
            message="仅失败的后继任务作业可人工重试",
            message_key="errors.autotask.successor_job_retry_not_allowed",
        )
    job.status = SuccessorJobStatus.PENDING
    job.attempt_count = 0
    job.next_attempt_at = datetime.now(UTC)
    job.last_error_code = None
    job.last_error_message = None
    await db.commit()
    await db.refresh(job)
    return job


class SuccessorJobProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._poll_interval = settings.SUCCESSOR_JOB_POLL_INTERVAL_SECONDS
        self._batch_size = settings.SUCCESSOR_JOB_BATCH_SIZE
        self._max_attempts = settings.SUCCESSOR_JOB_MAX_ATTEMPTS
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run(),
            name="task-successor-job-processor",
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.process_once()
            except Exception:
                logger.exception("后继任务作业轮询失败")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval,
                )
            except TimeoutError:
                continue

    async def process_once(self) -> int:
        now = datetime.now(UTC)
        async with self._session_factory() as db, db.begin():
            jobs = list(
                (
                    await db.execute(
                        select(TaskSuccessorJob)
                        .where(
                            TaskSuccessorJob.status.in_(
                                [
                                    SuccessorJobStatus.PENDING,
                                    SuccessorJobStatus.RETRYING,
                                ]
                            ),
                            or_(
                                TaskSuccessorJob.next_attempt_at.is_(None),
                                TaskSuccessorJob.next_attempt_at <= now,
                            ),
                            not_deleted(TaskSuccessorJob),
                        )
                        .order_by(TaskSuccessorJob.created_at.asc())
                        .limit(self._batch_size)
                        .with_for_update(skip_locked=True)
                    )
                )
                .scalars()
                .all()
            )
            for job in jobs:
                await self._process_job(db, job, now=now)
            return len(jobs)

    async def _process_job(
        self,
        db: AsyncSession,
        job: TaskSuccessorJob,
        *,
        now: datetime,
    ) -> None:
        job.status = SuccessorJobStatus.PROCESSING
        job.attempt_count += 1
        try:
            await self._create_successor_task(db, job)
        except SuccessorJobError as exc:
            self._record_failure(job, exc, now=now)

    def _record_failure(
        self,
        job: TaskSuccessorJob,
        error: SuccessorJobError,
        *,
        now: datetime,
    ) -> None:
        job.last_error_code = error.code
        job.last_error_message = error.safe_message
        if error.retryable and job.attempt_count < self._max_attempts:
            delay_index = min(
                job.attempt_count - 1,
                len(_RETRY_DELAYS_SECONDS) - 1,
            )
            job.status = SuccessorJobStatus.RETRYING
            job.next_attempt_at = now + timedelta(seconds=_RETRY_DELAYS_SECONDS[delay_index])
        else:
            job.status = SuccessorJobStatus.FAILED
            job.next_attempt_at = None

    async def _create_successor_task(
        self,
        db: AsyncSession,
        job: TaskSuccessorJob,
    ) -> None:
        source_task = (
            await db.execute(
                select(AutomationTask).where(
                    AutomationTask.id == job.source_task_id,
                    AutomationTask.tenant_id == job.tenant_id,
                    not_deleted(AutomationTask),
                )
            )
        ).scalar_one_or_none()
        source_run = (
            await db.execute(
                select(RpaRun).where(
                    RpaRun.id == job.source_run_id,
                    RpaRun.task_id == job.source_task_id,
                    not_deleted(RpaRun),
                )
            )
        ).scalar_one_or_none()
        target_row = (
            await db.execute(
                select(WorkflowBinding, PortalAccount, WorkflowTemplate)
                .join(
                    PortalAccount,
                    WorkflowBinding.portal_account_id == PortalAccount.id,
                )
                .join(
                    WorkflowTemplate,
                    WorkflowBinding.workflow_template_id == WorkflowTemplate.id,
                )
                .where(
                    WorkflowBinding.id == job.target_workflow_binding_id,
                    PortalAccount.tenant_id == job.tenant_id,
                    WorkflowTemplate.tenant_id == job.tenant_id,
                    not_deleted(WorkflowBinding),
                    not_deleted(PortalAccount),
                    not_deleted(WorkflowTemplate),
                )
            )
        ).one_or_none()
        if source_task is None or source_run is None:
            raise SuccessorJobError(
                "SUCCESSOR_SOURCE_NOT_FOUND",
                "来源 Task 或 Run 不存在",
            )
        if source_run.status != RunStatus.SUCCESS or source_task.status != TaskStatus.SUCCESS:
            raise SuccessorJobError(
                "SUCCESSOR_SOURCE_NOT_SUCCESS",
                "仅成功的来源 Task 和 Run 可以创建后继任务",
            )
        if target_row is None:
            raise SuccessorJobError(
                "SUCCESSOR_BINDING_NOT_FOUND",
                "后继 Workflow Binding 不存在",
            )
        target_binding, _, target_template = target_row
        if target_binding.id == source_task.workflow_binding_id:
            raise SuccessorJobError(
                "SUCCESSOR_BINDING_SELF_REFERENCE",
                "后继 Workflow Binding 不能指向来源 Binding",
            )
        if target_binding.status != BindingStatus.ENABLED:
            raise SuccessorJobError(
                "SUCCESSOR_BINDING_DISABLED",
                "后继 Workflow Binding 当前未启用",
                retryable=True,
            )
        if target_binding.portal_account_id != source_task.portal_account_id:
            raise SuccessorJobError(
                "SUCCESSOR_PORTAL_MISMATCH",
                "来源任务与后继 Binding 的 Portal 不一致",
            )
        if not target_binding.rpa_flow_version_id or not target_binding.flow_checksum_snapshot:
            raise SuccessorJobError(
                "SUCCESSOR_FLOW_SNAPSHOT_MISSING",
                "后继 Binding 缺少精确 Flow 版本快照",
            )
        successor_definition = _SUPPORTED_SUCCESSORS.get(job.input_mapper)
        if successor_definition is None:
            raise SuccessorJobError(
                "SUCCESSOR_INPUT_MAPPER_UNSUPPORTED",
                "后继输入映射器不受支持",
            )
        _, target_workflow_code = successor_definition
        if target_template.code != target_workflow_code:
            raise SuccessorJobError(
                "SUCCESSOR_WORKFLOW_CODE_INVALID",
                "后继模板类型不受支持",
            )

        if job.input_mapper == SUCCESSOR_INPUT_MAPPER:
            input_data = map_delivery_confirmation_input(
                source_run.output,
                source_task_id=source_task.id,
                source_run_id=source_run.id,
            )
            child_title = f"2. 在 SRM 系统中填入交货日期并确认 - {input_data['po_no']}"
            child_status = TaskStatus.DRAFT
            queue_immediately = False
        else:
            input_data = map_attachment_upload_input(source_run.output)
            child_title = f"3. 上传订单附件 - {input_data['po_no']}"
            child_status = TaskStatus.QUEUED
            queue_immediately = True
        child = AutomationTask(
            tenant_id=source_task.tenant_id,
            title=child_title,
            task_type=target_template.code,
            portal_account_id=target_binding.portal_account_id,
            workflow_binding_id=target_binding.id,
            entity_type=source_task.entity_type,
            erp_entity_code=source_task.erp_entity_code,
            erp_entity_name=source_task.erp_entity_name,
            status=child_status,
            priority=source_task.priority,
            input=dumps_json(input_data),
            created_by=source_task.created_by,
            assigned_to=source_task.assigned_to or source_task.created_by,
            source_task_id=source_task.id,
            source_run_id=source_run.id,
        )
        db.add(child)
        await db.flush()
        if queue_immediately:
            db.add(
                RpaRun(
                    task_id=child.id,
                    rpa_flow_id=target_binding.rpa_flow_id,
                    status=RunStatus.QUEUED,
                )
            )
        db.add(
            TaskMessage(
                task_id=child.id,
                role="system",
                content=(
                    f"由任务 {source_task.id} 的成功运行自动创建" + ("并进入执行队列" if queue_immediately else "")
                ),
                created_by=source_task.created_by,
            )
        )
        db.add(
            TaskMessage(
                task_id=source_task.id,
                role="system",
                content=f"已创建后继任务：{child.title}",
                created_by=source_task.created_by,
            )
        )
        job.successor_task_id = child.id
        job.status = SuccessorJobStatus.SUCCEEDED
        job.next_attempt_at = None
        job.last_error_code = None
        job.last_error_message = None
