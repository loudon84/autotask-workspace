"""独立定时器到期通知。任务开发 register(target, 入口)；内核只 notify。"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

TimerCallback = Callable[[], Awaitable[None]]

_registry: dict[str, TimerCallback] = {}


def register(target: str, fn: TimerCallback) -> None:
    _registry[target] = fn


def unregister(target: str) -> None:
    _registry.pop(target, None)


def clear() -> None:
    _registry.clear()


async def notify(target: str) -> bool:
    """到点通知。返回是否有注册入口；入口抛错向上抛，由调用方记录。"""
    # @lat: [[domain#SchedulerJob]]
    fn = _registry.get(target)
    if fn is None:
        logger.info("timer due, no listener target=%s", target)
        return False
    await fn()
    return True
