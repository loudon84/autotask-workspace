"""Automation task state machine."""

from app.core.exceptions import BadRequestError
from app.models.automation_task import AutomationTask
from app.models.enums import TaskStatus

TRANSITIONS: dict[str, set[str]] = {
    TaskStatus.DRAFT: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.QUEUED, TaskStatus.DRAFT, TaskStatus.CANCELLED},
    TaskStatus.QUEUED: {TaskStatus.LEASED, TaskStatus.CANCELLED},
    TaskStatus.LEASED: {TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.QUEUED,
        TaskStatus.WAITING_HUMAN,
        TaskStatus.SUCCESS,
        TaskStatus.PARTIAL_SUCCESS,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING_HUMAN: {
        TaskStatus.HUMAN_OPERATING,
        TaskStatus.SUCCESS_MANUAL,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.HUMAN_OPERATING: {
        TaskStatus.SUCCESS_MANUAL,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.SUCCESS: set(),
    TaskStatus.SUCCESS_MANUAL: set(),
    TaskStatus.PARTIAL_SUCCESS: set(),
    TaskStatus.FAILED: {TaskStatus.READY, TaskStatus.QUEUED},
    TaskStatus.CANCELLED: set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, set())


def transition(task: AutomationTask, target_status: str) -> AutomationTask:
    if not can_transition(task.status, target_status):
        raise BadRequestError(
            message=f"任务状态不允许从 {task.status} 转换到 {target_status}",
            message_key="errors.autotask.invalid_status_transition",
            message_params={"from_status": task.status, "to_status": target_status},
        )
    task.status = target_status
    return task
