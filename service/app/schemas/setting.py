"""调度器设置（autotask_settings）请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.cron_schedule import CronParseError, CronSchedule


def _validate_cron(value: str) -> str:
    try:
        CronSchedule.parse(value).next_after(datetime.now())
    except CronParseError as exc:
        raise ValueError(str(exc)) from None
    return value


class SignPollSettings(BaseModel):
    enabled: bool
    cron: str

    @field_validator("cron")
    @classmethod
    def _cron_valid(cls, value: str) -> str:
        return _validate_cron(value)


class ScanSettings(BaseModel):
    enabled: bool
    cron: str

    @field_validator("cron")
    @classmethod
    def _cron_valid(cls, value: str) -> str:
        return _validate_cron(value)


class BoePackSettings(BaseModel):
    enabled: bool
    cron: str

    @field_validator("cron")
    @classmethod
    def _cron_valid(cls, value: str) -> str:
        return _validate_cron(value)


class SchedulerSettingsResponse(BaseModel):
    sign_poll: SignPollSettings
    scan: ScanSettings
    boe_pack: BoePackSettings
    next_run_at: dict[str, str | None] = Field(
        default_factory=dict,
        description="各调度器下次触发时刻（ISO 本地时间）；未启用为 null",
    )


class SchedulerSettingsUpdate(BaseModel):
    sign_poll: SignPollSettings | None = None
    scan: ScanSettings | None = None
    boe_pack: BoePackSettings | None = None
