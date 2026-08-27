from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field, model_validator

from app.schemas.common import CamelModel


class WorkerRegisterRequest(CamelModel):
    worker_id: str = Field(validation_alias=AliasChoices("worker_id", "workerId"), serialization_alias="workerId")
    worker_type: str = Field(validation_alias=AliasChoices("worker_type", "workerType"), serialization_alias="workerType")
    device_name: str = Field(validation_alias=AliasChoices("device_name", "deviceName"), serialization_alias="deviceName")
    user_id: str | None = Field(
        None, validation_alias=AliasChoices("user_id", "userId"), serialization_alias="userId"
    )
    app_version: str | None = Field(
        None, validation_alias=AliasChoices("app_version", "appVersion"), serialization_alias="appVersion"
    )
    agent_version: str | None = Field(
        None, validation_alias=AliasChoices("agent_version", "agentVersion"), serialization_alias="agentVersion"
    )
    os: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class WorkerLeaseRequest(CamelModel):
    worker_id: str = Field(validation_alias=AliasChoices("worker_id", "workerId"), serialization_alias="workerId")
    capabilities: list[str] = Field(default_factory=list)
    limit: int = 1


class BrowserSessionConfig(CamelModel):
    mode: str = "MANAGED"
    headless: bool = True
    channel: str = "chromium"
    profile_ref: str | None = Field(None, serialization_alias="profileRef")
    cdp_endpoint_ref: str | None = Field(None, serialization_alias="cdpEndpointRef")
    close_policy: str = Field("CLOSE_ON_FINISH", serialization_alias="closePolicy")


class LeaseCommandConfig(CamelModel):
    portal_url: str = Field(serialization_alias="portalUrl")
    browser_session: BrowserSessionConfig = Field(serialization_alias="browserSession")
    dry_run: bool = Field(
        default=False,
        validation_alias=AliasChoices("dry_run", "dryRun"),
        serialization_alias="dryRun",
    )
    customer_name: str | None = Field(None, serialization_alias="customerName")
    customer_code: str | None = Field(None, serialization_alias="customerCode")
    business_entity: str | None = Field(None, serialization_alias="businessEntity")
    ou: str | None = Field(None, serialization_alias="ou")
    sdms_base_url: str | None = Field(None, serialization_alias="sdmsBaseUrl")
    erp_base_url: str | None = Field(None, serialization_alias="erpBaseUrl")
    oa_base_url: str | None = Field(None, serialization_alias="oaBaseUrl")
    doc_base_url: str | None = Field(None, serialization_alias="docBaseUrl")
    erp_client_id: str | None = Field(None, serialization_alias="erpClientId")
    erp_client_secret: str | None = Field(None, serialization_alias="erpClientSecret")
    searches: list[dict[str, Any]] | None = None


class LeaseCredentials(CamelModel):
    username: str
    password: str


class WorkerLeaseResponse(CamelModel):
    task_id: str = Field(serialization_alias="taskId")
    run_id: str = Field(serialization_alias="runId")
    lease_id: str = Field(serialization_alias="leaseId")
    workflow_binding_id: str = Field(serialization_alias="workflowBindingId")
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    rpa_flow_id: str = Field(serialization_alias="rpaFlowId")
    input: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = Field(serialization_alias="tenantId")
    workflow_template_id: str = Field(serialization_alias="workflowTemplateId")
    workflow_code: str = Field(serialization_alias="workflowCode")
    rpa_engine_type: str = Field(serialization_alias="rpaEngineType")
    rpa_flow_version: str = Field(serialization_alias="rpaFlowVersion")
    credential_ref: str = Field(serialization_alias="credentialRef")
    credentials: LeaseCredentials | None = None
    config: LeaseCommandConfig
    lease_expires_at: datetime = Field(serialization_alias="leaseExpiresAt")


class WorkerLeaseRenewRequest(CamelModel):
    worker_id: str = Field(validation_alias=AliasChoices("worker_id", "workerId"), serialization_alias="workerId")
    lease_id: str = Field(validation_alias=AliasChoices("lease_id", "leaseId"), serialization_alias="leaseId")


class WorkerLeaseRenewResponse(CamelModel):
    lease_expires_at: datetime = Field(serialization_alias="leaseExpiresAt")


class RunEventCreate(CamelModel):
    worker_id: str | None = Field(
        None, validation_alias=AliasChoices("worker_id", "workerId"), serialization_alias="workerId"
    )
    type: str
    level: str = "INFO"
    message: str
    payload: dict[str, Any] | None = None


class RunArtifactCreate(CamelModel):
    type: str
    name: str
    storage_key: str = Field(validation_alias=AliasChoices("storage_key", "storageKey"), serialization_alias="storageKey")
    size: int = 0
    mime_type: str | None = Field(
        None, validation_alias=AliasChoices("mime_type", "mimeType"), serialization_alias="mimeType"
    )


class IntegrationCallCreate(CamelModel):
    """Worker 回调：记录一次接口调用。run_id 从 path 取。"""

    system: str
    method: str
    url: str
    request_body: str | None = Field(
        None, validation_alias=AliasChoices("request_body", "requestBody"), serialization_alias="requestBody"
    )
    response_body: str | None = Field(
        None, validation_alias=AliasChoices("response_body", "responseBody"), serialization_alias="responseBody"
    )
    status_code: int | None = Field(
        None, validation_alias=AliasChoices("status_code", "statusCode"), serialization_alias="statusCode"
    )
    error_code: str | None = Field(
        None, validation_alias=AliasChoices("error_code", "errorCode"), serialization_alias="errorCode"
    )
    duration_ms: int | None = Field(
        None, validation_alias=AliasChoices("duration_ms", "durationMs"), serialization_alias="durationMs"
    )


class RunFinishRequest(CamelModel):
    status: str
    error_code: str | None = Field(
        None, validation_alias=AliasChoices("error_code", "errorCode"), serialization_alias="errorCode"
    )
    error_message: str | None = Field(
        None, validation_alias=AliasChoices("error_message", "errorMessage"), serialization_alias="errorMessage"
    )
    output: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_output_status(self):
        if self.output is not None and self.status != "SUCCESS":
            raise ValueError("Run output is allowed only for SUCCESS")
        return self


class WorkerArtifactUploadUrlRequest(CamelModel):
    worker_id: str = Field(validation_alias=AliasChoices("worker_id", "workerId"), serialization_alias="workerId")
    task_id: str = Field(validation_alias=AliasChoices("task_id", "taskId"), serialization_alias="taskId")
    run_id: str = Field(validation_alias=AliasChoices("run_id", "runId"), serialization_alias="runId")
    name: str
    mime_type: str | None = Field(
        None, validation_alias=AliasChoices("mime_type", "mimeType"), serialization_alias="mimeType"
    )
