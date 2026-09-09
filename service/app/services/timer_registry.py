"""独立定时器到期通知。任务开发 register(target, 入口)；内核只 notify。"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

TimerCallback = Callable[[], Awaitable[str | None]]

_registry: dict[str, TimerCallback] = {}


class TimerBusinessError(RuntimeError):
    """入口主动失败：timer_runs 记 FAILED，error 给人看的摘要（禁止写验证码）。"""


def register(target: str, fn: TimerCallback) -> None:
    _registry[target] = fn


def unregister(target: str) -> None:
    _registry.pop(target, None)


def clear() -> None:
    _registry.clear()


async def notify(target: str) -> tuple[bool, str | None]:
    """到点通知。返回 (是否有入口, 摘要)。入口抛错向上抛，由调用方记录。"""
    # @lat: [[domain#SchedulerJob]]
    fn = _registry.get(target)
    if fn is None:
        logger.info("timer due, no listener target=%s", target)
        return False, None
    summary = await fn()
    text = summary.strip() if isinstance(summary, str) and summary.strip() else None
    return True, text
