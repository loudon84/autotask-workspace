import json
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field, field_validator

from app.schemas.common import CamelModel


class RpaRunResponse(CamelModel):
    id: str
    task_id: str = Field(serialization_alias="taskId")
    rpa_flow_id: str = Field(serialization_alias="rpaFlowId")
    rpa_worker_id: str | None = Field(None, serialization_alias="rpaWorkerId")
    lease_id: str | None = Field(None, serialization_alias="leaseId")
    status: str
    current_step_id: str | None = Field(None, serialization_alias="currentStepId")
    started_at: datetime | None = Field(None, serialization_alias="startedAt")
    ended_at: datetime | None = Field(None, serialization_alias="endedAt")
    error_code: str | None = Field(None, serialization_alias="errorCode")
    error_message: str | None = Field(None, serialization_alias="errorMessage")
    output: dict[str, Any] | None = None


class StepRunResponse(CamelModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    step_id: str = Field(serialization_alias="stepId")
    step_name: str = Field("", serialization_alias="stepName")
    status: str
    output: dict[str, Any] | None = None

    @field_validator("output", mode="before")
    @classmethod
    def parse_output(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value or "{}")
        return value


class RunEventResponse(CamelModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    task_id: str = Field(serialization_alias="taskId")
    worker_id: str | None = Field(None, serialization_alias="workerId")
    type: str
    level: str
    message: str
    payload: dict[str, Any] | None = None
    created_at: datetime = Field(serialization_alias="createdAt")

    @field_validator("payload", mode="before")
    @classmethod
    def parse_payload(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value or "{}")
        return value


class HumanActionResponse(CamelModel):
    id: str
    task_id: str = Field(serialization_alias="taskId")
    run_id: str | None = Field(None, serialization_alias="runId")
    type: str
    status: str
    title: str
    instruction: str
    target_url: str | None = Field(None, serialization_alias="targetUrl")
    payload: dict[str, Any] | None = None
    created_at: datetime = Field(serialization_alias="createdAt")
    opened_by: str | None = Field(None, serialization_alias="openedBy")
    opened_at: datetime | None = Field(None, serialization_alias="openedAt")
    confirmed_by: str | None = Field(None, serialization_alias="confirmedBy")
    confirmed_at: datetime | None = Field(None, serialization_alias="confirmedAt")

    @field_validator("payload", mode="before")
    @classmethod
    def parse_payload(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value or "{}")
        return value


class HumanActionConfirmRequest(CamelModel):
    resume_running: bool = Field(
        False,
        validation_alias=AliasChoices("resume_running", "resumeRunning"),
        serialization_alias="resumeRunning",
    )


class ArtifactResponse(CamelModel):
    id: str
    tenant_id: str = Field(serialization_alias="tenantId")
    task_id: str = Field(serialization_alias="taskId")
    run_id: str | None = Field(None, serialization_alias="runId")
    type: str
    name: str
    storage_key: str = Field(serialization_alias="storageKey")
    size: int
    mime_type: str | None = Field(None, serialization_alias="mimeType")
    created_by: str | None = Field(None, serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")


class ArtifactUploadUrlRequest(CamelModel):
    task_id: str = Field(validation_alias=AliasChoices("task_id", "taskId"), serialization_alias="taskId")
    run_id: str | None = Field(
        None, validation_alias=AliasChoices("run_id", "runId"), serialization_alias="runId"
    )
    name: str
    mime_type: str | None = Field(
        None, validation_alias=AliasChoices("mime_type", "mimeType"), serialization_alias="mimeType"
    )


class ArtifactUploadUrlResponse(CamelModel):
    upload_url: str = Field(serialization_alias="uploadUrl")
    storage_key: str = Field(serialization_alias="storageKey")


class ArtifactDownloadUrlResponse(CamelModel):
    url: str = ""


class RpaWorkerClientResponse(CamelModel):
    id: str
    name: str
    status: str
    current_task_count: int = Field(0, serialization_alias="currentTaskCount")
    browser_count: int = Field(0, serialization_alias="browserCount")
    cpu_usage: int = Field(0, serialization_alias="cpuUsage")
    memory_usage: int = Field(0, serialization_alias="memoryUsage")
    last_heartbeat_at: datetime = Field(serialization_alias="lastHeartbeatAt")


class RpaWorkerResponse(CamelModel):
    id: str
    worker_type: str = Field(serialization_alias="workerType")
    device_name: str = Field(serialization_alias="deviceName")
    user_id: str | None = Field(None, serialization_alias="userId")
    status: str
    capabilities: list[str]
    app_version: str | None = Field(None, serialization_alias="appVersion")
    agent_version: str | None = Field(None, serialization_alias="agentVersion")
    os: str | None = None
    current_run_id: str | None = Field(None, serialization_alias="currentRunId")
    last_heartbeat_at: datetime = Field(serialization_alias="lastHeartbeatAt")

    @field_validator("capabilities", mode="before")
    @classmethod
    def parse_capabilities(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return json.loads(value or "[]")
        return value or []
