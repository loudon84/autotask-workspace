from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class TimerResponse(CamelModel):
    id: str
    name: str
    cron: str
    enabled: bool
    next_run_at: datetime | None = Field(None, serialization_alias="nextRunAt")


class TimerUpdate(CamelModel):
    name: str | None = None
    enabled: bool | None = None
    cron: str | None = None


class TimerRunItem(CamelModel):
    id: str
    status: str
    triggered_at: datetime = Field(serialization_alias="triggeredAt")
    finished_at: datetime | None = Field(None, serialization_alias="finishedAt")
    error: str | None = None


class TimerRunPage(CamelModel):
    items: list[TimerRunItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(20, serialization_alias="pageSize")
