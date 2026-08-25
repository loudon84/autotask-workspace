"""调度器运行时配置（autotask_settings 表权威，.env 仅作首次回退默认值）。

回签轮询 / 定时扫单统一为 cron 触发模型：开关 + 5 段 cron 表达式（本地时间）。
`*/30 * * * *` = 每半小时，`0 8 * * *` = 每天 8 点，`0 8 * * 1-5` = 工作日 8 点。
经 /settings/schedulers API 修改后由调度器热加载，无需重启。
后继任务处理器（SUCCESSOR_JOB_*）不在此列，仍由 .env 控制。
"""

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.autotask_setting import AutotaskSetting
from app.models.base import not_deleted
from app.services.cron_schedule import CronSchedule
from app.services.json_utils import dumps_json

# 配置键（存 autotask_settings.key，value 为 JSON 文本）
KEY_SIGN_POLL_ENABLED = "scheduler.signPoll.enabled"
KEY_SIGN_POLL_CRON = "scheduler.signPoll.cron"
KEY_SCAN_ENABLED = "scheduler.scan.enabled"
KEY_SCAN_CRON = "scheduler.scan.cron"

# 调度配置是全局一份，不跟登录组织走。表上仍有 tenant_id 列，固定写这个值。
SCHEDULER_TENANT_ID = "seed-tenant-001"

# 默认表达式（表与 .env 均无值时的兜底）
DEFAULT_SIGN_POLL_CRON = "*/30 * * * *"
DEFAULT_SCAN_CRON = "0 8 * * *"


@dataclass
class SchedulerConfig:
    sign_poll_enabled: bool
    sign_poll_cron: str
    scan_enabled: bool
    scan_cron: str

    def parsed_sign_poll(self) -> CronSchedule:
        return CronSchedule.parse(self.sign_poll_cron)

    def parsed_scan(self) -> CronSchedule:
        return CronSchedule.parse(self.scan_cron)


def _interval_seconds_to_cron(seconds: float) -> str:
    """把 .env 的轮询间隔（秒）折算为分钟粒度 cron。"""
    minutes = max(1, round(seconds / 60))
    return f"*/{minutes} * * * *"


def _default_config() -> SchedulerConfig:
    sign_cron = _interval_seconds_to_cron(settings.SIGN_POLL_INTERVAL_SECONDS)
    scan_cron = f"{settings.SCAN_JOB_MINUTE} {settings.SCAN_JOB_HOUR} * * *"
    return SchedulerConfig(
        sign_poll_enabled=settings.SIGN_POLL_JOB_ENABLED,
        sign_poll_cron=sign_cron,
        scan_enabled=settings.SCAN_JOB_ENABLED,
        scan_cron=scan_cron,
    )


async def get_scheduler_config(db: AsyncSession) -> SchedulerConfig:
    """读全局调度配置；表中缺失或非法的键回退 .env 默认。"""
    defaults = _default_config()
    keys = [KEY_SIGN_POLL_ENABLED, KEY_SIGN_POLL_CRON, KEY_SCAN_ENABLED, KEY_SCAN_CRON]
    rows = (
        await db.execute(
            select(AutotaskSetting.key, AutotaskSetting.value).where(
                AutotaskSetting.tenant_id == SCHEDULER_TENANT_ID,
                AutotaskSetting.key.in_(keys),
                not_deleted(AutotaskSetting),
            )
        )
    ).all()
    stored: dict[str, object] = {}
    for key, raw in rows:
        try:
            stored[key] = json.loads(raw)
        except (TypeError, ValueError):
            continue

    def _bool(key: str, fallback: bool) -> bool:
        value = stored.get(key, fallback)
        return value if isinstance(value, bool) else fallback

    def _cron(key: str, fallback: str) -> str:
        value = stored.get(key, fallback)
        if not isinstance(value, str):
            return fallback
        try:
            CronSchedule.parse(value)
        except ValueError:
            return fallback
        return value

    return SchedulerConfig(
        sign_poll_enabled=_bool(KEY_SIGN_POLL_ENABLED, defaults.sign_poll_enabled),
        sign_poll_cron=_cron(KEY_SIGN_POLL_CRON, defaults.sign_poll_cron),
        scan_enabled=_bool(KEY_SCAN_ENABLED, defaults.scan_enabled),
        scan_cron=_cron(KEY_SCAN_CRON, defaults.scan_cron),
    )


async def update_scheduler_config(
    db: AsyncSession,
    config: SchedulerConfig,
) -> SchedulerConfig:
    """把页面提交的配置写到全局调度行（cron 先校验可解析）。"""
    CronSchedule.parse(config.sign_poll_cron)
    CronSchedule.parse(config.scan_cron)
    values = {
        KEY_SIGN_POLL_ENABLED: config.sign_poll_enabled,
        KEY_SIGN_POLL_CRON: config.sign_poll_cron,
        KEY_SCAN_ENABLED: config.scan_enabled,
        KEY_SCAN_CRON: config.scan_cron,
    }
    existing = {
        row.key: row
        for row in (
            await db.execute(
                select(AutotaskSetting).where(
                    AutotaskSetting.tenant_id == SCHEDULER_TENANT_ID,
                    AutotaskSetting.key.in_(values.keys()),
                    not_deleted(AutotaskSetting),
                )
            )
        ).scalars()
    }
    for key, value in values.items():
        row = existing.get(key)
        if row is not None:
            row.value = dumps_json(value)
        else:
            db.add(
                AutotaskSetting(
                    tenant_id=SCHEDULER_TENANT_ID,
                    key=key,
                    value=dumps_json(value),
                )
            )
    await db.flush()
    return config
