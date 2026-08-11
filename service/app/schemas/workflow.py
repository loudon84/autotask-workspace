import json
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import CamelModel


class WorkflowTemplateCreate(CamelModel):
    name: str
    code: str
    description: str | None = None
    entity_type: str = Field(serialization_alias="entityType")
    category: str = ""
    status: str = "DRAFT"
    version: str = "1.0.0"
    input_schema: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="inputSchema")
    business_steps: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="businessSteps")


class WorkflowTemplateUpdate(CamelModel):
    name: str | None = None
    description: str | None = None
    entity_type: str | None = Field(None, serialization_alias="entityType")
    category: str | None = None
    status: str | None = None
    version: str | None = None
    input_schema: list[dict[str, Any]] | None = Field(None, serialization_alias="inputSchema")
    business_steps: list[dict[str, Any]] | None = Field(None, serialization_alias="businessSteps")


class WorkflowTemplateResponse(CamelModel):
    id: str
    tenant_id: str = Field(serialization_alias="tenantId")
    name: str
    code: str
    description: str | None = None
    entity_type: str = Field(serialization_alias="entityType")
    category: str
    status: str
    version: str
    input_schema: list[dict[str, Any]] = Field(serialization_alias="inputSchema")
    business_steps: list[dict[str, Any]] = Field(serialization_alias="businessSteps")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    @field_validator("input_schema", "business_steps", mode="before")
    @classmethod
    def parse_json_list(cls, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, str):
            return json.loads(value or "[]")
        return value or []


class WorkflowBindingCreate(CamelModel):
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    workflow_template_id: str = Field(serialization_alias="workflowTemplateId")
    workflow_template_version: str = Field(serialization_alias="workflowTemplateVersion")
    rpa_engine_type: str = Field("PLAYWRIGHT_CDP", serialization_alias="rpaEngineType")
    rpa_flow_id: str = Field(serialization_alias="rpaFlowId")
    rpa_flow_version: str = Field("1.0.0", serialization_alias="rpaFlowVersion")
    status: str = "ENABLED"
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowBindingUpdate(CamelModel):
    workflow_template_version: str | None = Field(None, serialization_alias="workflowTemplateVersion")
    rpa_engine_type: str | None = Field(None, serialization_alias="rpaEngineType")
    rpa_flow_id: str | None = Field(None, serialization_alias="rpaFlowId")
    rpa_flow_version: str | None = Field(None, serialization_alias="rpaFlowVersion")
    status: str | None = None
    config: dict[str, Any] | None = None


class WorkflowBindingResponse(CamelModel):
    id: str
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    workflow_template_id: str = Field(serialization_alias="workflowTemplateId")
    workflow_template_version: str = Field(serialization_alias="workflowTemplateVersion")
    rpa_engine_type: str = Field(serialization_alias="rpaEngineType")
    rpa_flow_id: str = Field(serialization_alias="rpaFlowId")
    rpa_flow_version: str = Field(serialization_alias="rpaFlowVersion")
    rpa_flow_version_id: str | None = Field(None, serialization_alias="rpaFlowVersionId")
    flow_checksum_snapshot: str | None = Field(None, serialization_alias="flowChecksumSnapshot")
    status: str
    config: dict[str, Any]
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    @field_validator("config", mode="before")
    @classmethod
    def parse_config(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            return json.loads(value or "{}")
        return value or {}
