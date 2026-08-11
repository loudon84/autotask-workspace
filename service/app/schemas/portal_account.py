import json
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.models.enums import ClientOpenMode, EntityType, PortalAccountStatus
from app.schemas.common import CamelModel

_HTTP_URL_PREFIXES = ("http://", "https://")


def _validate_http_url(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("portalUrl 不能为空")
    if not normalized.startswith(_HTTP_URL_PREFIXES):
        raise ValueError("portalUrl 必须是 http 或 https 地址")
    return normalized


def _validate_non_empty(value: str, field_label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_label} 不能为空")
    return normalized


class PortalAccountCreate(CamelModel):
    entity_type: EntityType = Field(alias="entityType")
    erp_entity_code: str = Field(alias="erpEntityCode")
    erp_entity_name: str = Field(alias="erpEntityName")
    portal_name: str = Field(alias="portalName")
    portal_url: str = Field(alias="portalUrl")
    login_account: str = Field(alias="loginAccount")
    credential_ref: str | None = Field(None, alias="credentialRef")
    client_open_mode: ClientOpenMode = Field(
        ClientOpenMode.WEBCONTENTS,
        alias="clientOpenMode",
    )
    client_session_partition: str = Field("", alias="clientSessionPartition")
    rpa_profile_id: str | None = Field(None, alias="rpaProfileId")
    status: PortalAccountStatus = PortalAccountStatus.ENABLED
    owner_dept_id: str | None = Field(None, alias="ownerDeptId")

    @field_validator("portal_url")
    @classmethod
    def validate_portal_url(cls, value: str) -> str:
        return _validate_http_url(value)

    @field_validator("erp_entity_code", "erp_entity_name", "portal_name", "login_account")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        labels = {
            "erp_entity_code": "erpEntityCode",
            "erp_entity_name": "erpEntityName",
            "portal_name": "portalName",
            "login_account": "loginAccount",
        }
        return _validate_non_empty(value, labels.get(info.field_name, info.field_name))


class PortalAccountUpdate(CamelModel):
    entity_type: EntityType | None = Field(None, alias="entityType")
    erp_entity_code: str | None = Field(None, alias="erpEntityCode")
    erp_entity_name: str | None = Field(None, alias="erpEntityName")
    portal_name: str | None = Field(None, alias="portalName")
    portal_url: str | None = Field(None, alias="portalUrl")
    login_account: str | None = Field(None, alias="loginAccount")
    credential_ref: str | None = Field(None, alias="credentialRef")
    client_open_mode: ClientOpenMode | None = Field(None, alias="clientOpenMode")
    client_session_partition: str | None = Field(None, alias="clientSessionPartition")
    rpa_profile_id: str | None = Field(None, alias="rpaProfileId")
    status: PortalAccountStatus | None = None
    owner_dept_id: str | None = Field(None, alias="ownerDeptId")

    @field_validator("portal_url")
    @classmethod
    def validate_portal_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_http_url(value)

    @field_validator("erp_entity_code", "erp_entity_name", "portal_name", "login_account")
    @classmethod
    def validate_optional_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return value
        labels = {
            "erp_entity_code": "erpEntityCode",
            "erp_entity_name": "erpEntityName",
            "portal_name": "portalName",
            "login_account": "loginAccount",
        }
        return _validate_non_empty(value, labels.get(info.field_name, info.field_name))


class PortalAccountResponse(CamelModel):
    id: str
    tenant_id: str = Field(serialization_alias="tenantId")
    entity_type: str = Field(serialization_alias="entityType")
    erp_entity_code: str = Field(serialization_alias="erpEntityCode")
    erp_entity_name: str = Field(serialization_alias="erpEntityName")
    portal_name: str = Field(serialization_alias="portalName")
    portal_url: str = Field(serialization_alias="portalUrl")
    login_account: str = Field(serialization_alias="loginAccount")
    client_open_mode: str = Field(serialization_alias="clientOpenMode")
    client_session_partition: str = Field(serialization_alias="clientSessionPartition")
    status: str
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class PortalListPageResponse(CamelModel):
    items: list[PortalAccountResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(20, serialization_alias="pageSize")


class PortalAccessGrantCreate(CamelModel):
    subject_type: str = Field(alias="subjectType")
    subject_id: str = Field(alias="subjectId")
    permissions: list[str]


class PortalAccessGrantResponse(CamelModel):
    id: str
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    subject_type: str = Field(serialization_alias="subjectType")
    subject_id: str = Field(serialization_alias="subjectId")
    permissions: list[str]
    granted_by: str = Field(serialization_alias="grantedBy")
    granted_at: str = Field(serialization_alias="grantedAt")

    @field_validator("permissions", mode="before")
    @classmethod
    def parse_permissions(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return json.loads(value or "[]")
        return value or []


class PortalTestOpenResponse(CamelModel):
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    portal_name: str = Field(serialization_alias="portalName")
    portal_url: str = Field(serialization_alias="portalUrl")
    client_open_mode: str = Field(serialization_alias="clientOpenMode")
    client_session_partition: str = Field(serialization_alias="clientSessionPartition")
    status: str
    allowed: bool = True
