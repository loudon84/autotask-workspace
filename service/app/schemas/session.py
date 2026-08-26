from pydantic import Field

from app.schemas.common import CamelModel


class SessionUser(CamelModel):
    id: str
    name: str
    email: str | None = None
    current_org_id: str | None = Field(None, serialization_alias="currentOrgId")
    portal_org_role: str | None = Field(None, serialization_alias="portalOrgRole")
    is_super_admin: bool = Field(False, serialization_alias="isSuperAdmin")
    is_task_admin: bool = Field(False, serialization_alias="isTaskAdmin")
