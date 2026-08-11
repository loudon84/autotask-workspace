import json
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import CamelModel


class AutomationTaskCreate(CamelModel):
    title: str
    task_type: str = Field(serialization_alias="taskType")
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    workflow_binding_id: str = Field(serialization_alias="workflowBindingId")
    entity_type: str = Field(serialization_alias="entityType")
    erp_entity_code: str = Field(serialization_alias="erpEntityCode")
    erp_entity_name: str = Field(serialization_alias="erpEntityName")
    priority: str = "NORMAL"
    input: dict[str, Any] = Field(default_factory=dict)
    assigned_to: str | None = Field(None, serialization_alias="assignedTo")


class AutomationTaskUpdate(CamelModel):
    title: str | None = None
    priority: str | None = None
    input: dict[str, Any] | None = None
    assigned_to: str | None = Field(None, serialization_alias="assignedTo")
    current_step: str | None = Field(None, serialization_alias="currentStep")
    progress: int | None = None


class AutomationTaskResponse(CamelModel):
    id: str
    tenant_id: str = Field(serialization_alias="tenantId")
    title: str
    task_type: str = Field(serialization_alias="taskType")
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    workflow_binding_id: str = Field(serialization_alias="workflowBindingId")
    entity_type: str = Field(serialization_alias="entityType")
    erp_entity_code: str = Field(serialization_alias="erpEntityCode")
    erp_entity_name: str = Field(serialization_alias="erpEntityName")
    status: str
    priority: str
    input: dict[str, Any]
    current_step: str | None = Field(None, serialization_alias="currentStep")
    progress: int
    created_by: str = Field(serialization_alias="createdBy")
    assigned_to: str | None = Field(None, serialization_alias="assignedTo")
    source_task_id: str | None = Field(None, serialization_alias="sourceTaskId")
    source_run_id: str | None = Field(None, serialization_alias="sourceRunId")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    @field_validator("input", mode="before")
    @classmethod
    def parse_input(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            return json.loads(value or "{}")
        return value or {}


class TaskMessageResponse(CamelModel):
    id: str
    task_id: str = Field(serialization_alias="taskId")
    role: str
    content: str
    created_at: datetime = Field(serialization_alias="createdAt")


class TaskListItemResponse(CamelModel):
    id: str
    title: str
    task_type: str = Field(serialization_alias="taskType")
    customer_name: str = Field(serialization_alias="customerName")
    portal_id: str = Field(serialization_alias="portalId")
    srm_portal_name: str = Field(serialization_alias="srmPortalName")
    workflow_template_id: str = Field(serialization_alias="workflowTemplateId")
    workflow_template_name: str = Field(serialization_alias="workflowTemplateName")
    status: str
    priority: str
    owner: str
    input: dict[str, Any]
    current_step: str | None = Field(None, serialization_alias="currentStep")
    progress: int
    source_task_id: str | None = Field(None, serialization_alias="sourceTaskId")
    source_run_id: str | None = Field(None, serialization_alias="sourceRunId")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TaskListPageResponse(CamelModel):
    items: list[TaskListItemResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(20, serialization_alias="pageSize")


class TaskHumanActionStatusResponse(CamelModel):
    task_id: str = Field(serialization_alias="taskId")
    status: str


class TaskConfirmHumanResponse(CamelModel):
    task_id: str = Field(serialization_alias="taskId")
    status: str
    confirmed_at: datetime = Field(serialization_alias="confirmedAt")


class TaskSuccessorJobResponse(CamelModel):
    id: str
    tenant_id: str = Field(serialization_alias="tenantId")
    source_task_id: str = Field(serialization_alias="sourceTaskId")
    source_run_id: str = Field(serialization_alias="sourceRunId")
    target_workflow_binding_id: str = Field(serialization_alias="targetWorkflowBindingId")
    input_mapper: str = Field(serialization_alias="inputMapper")
    status: str
    attempt_count: int = Field(serialization_alias="attemptCount")
    next_attempt_at: datetime | None = Field(None, serialization_alias="nextAttemptAt")
    last_error_code: str | None = Field(None, serialization_alias="lastErrorCode")
    last_error_message: str | None = Field(None, serialization_alias="lastErrorMessage")
    successor_task_id: str | None = Field(None, serialization_alias="successorTaskId")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
