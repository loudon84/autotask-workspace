"""Parse Binding config.schedule and build scheduler job names."""

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import UnprocessableError
from app.services.cron_schedule import CronParseError, CronSchedule


@dataclass(frozen=True)
class ScheduleDecl:
    enabled: bool
    cron: str
    process_name: str
    action_name: str


def build_job_name(portal_name: str, process_name: str, action_name: str) -> str:
    return f"{portal_name}-{process_name}-{action_name}"


def parse_schedule(config: dict[str, Any] | None) -> ScheduleDecl | None:
    """无 schedule 键返回 None；有则校验 cron / processName / actionName。"""
    if not isinstance(config, dict) or "schedule" not in config:
        return None
    raw = config.get("schedule")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise UnprocessableError(
            message="config.schedule 必须是对象",
            message_key="errors.autotask.invalid_schedule",
        )
    cron = str(raw.get("cron") or "").strip()
    process_name = str(
        raw.get("processName") or raw.get("process_name") or ""
    ).strip()
    action_name = str(raw.get("actionName") or raw.get("action_name") or "").strip()
    if not cron:
        raise UnprocessableError(
            message="config.schedule.cron 不能为空",
            message_key="errors.autotask.invalid_schedule",
        )
    if not process_name:
        raise UnprocessableError(
            message="config.schedule.processName 不能为空",
            message_key="errors.autotask.invalid_schedule",
        )
    if not action_name:
        raise UnprocessableError(
            message="config.schedule.actionName 不能为空",
            message_key="errors.autotask.invalid_schedule",
        )
    try:
        CronSchedule.parse(cron)
    except CronParseError as exc:
        raise UnprocessableError(
            message=f"非法 cron：{exc}",
            message_key="errors.autotask.invalid_schedule",
        ) from exc
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        enabled = str(enabled).lower() not in {"false", "0", "no"}
    return ScheduleDecl(
        enabled=bool(enabled),
        cron=cron,
        process_name=process_name,
        action_name=action_name,
    )
