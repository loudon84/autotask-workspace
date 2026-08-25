from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class SchedulerJobResponse(CamelModel):
    id: str
    binding_id: str = Field(serialization_alias="bindingId")
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    portal_name: str = Field(serialization_alias="portalName")
    name: str
    cron: str
    enabled: bool
    next_run_at: datetime | None = Field(None, serialization_alias="nextRunAt")


class SchedulerJobUpdate(CamelModel):
    enabled: bool | None = None
    cron: str | None = None


class SchedulerJobTaskItem(CamelModel):
    id: str
    title: str
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")


class SchedulerJobTaskPage(CamelModel):
    items: list[SchedulerJobTaskItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(20, serialization_alias="pageSize")
