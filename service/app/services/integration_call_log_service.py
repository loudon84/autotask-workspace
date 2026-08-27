"""接口调用日志 service：写入 + 按任务列出。"""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.integration_call_log import IntegrationCallLog
from app.models.rpa_run import RpaRun
from app.services.integration_redact import redact_and_truncate


async def record_call(
    db: AsyncSession,
    *,
    task_id: str,
    tenant_id: str,
    run_id: str | None,
    system: str,
    method: str,
    url: str,
    request_body: str | None = None,
    response_body: str | None = None,
    status_code: int | None = None,
    error_code: str | None = None,
    duration_ms: int | None = None,
    commit: bool = False,
) -> IntegrationCallLog:
    """写入前脱敏+截断，再 insert。

    Worker 路径：传 run_id，反查 RpaRun 得到 task_id/tenant_id。
    Task 侧调用方：直接传 task_id + tenant_id（run_id 可空）。
    """
    safe_url, req, resp, req_trunc, resp_trunc = redact_and_truncate(
        url=url, request_body=request_body, response_body=response_body
    )
    log = IntegrationCallLog(
        tenant_id=tenant_id,
        task_id=task_id,
        run_id=run_id,
        system=system,
        method=method.upper(),
        url=safe_url,
        request_body=req,
        response_body=resp,
        status_code=status_code,
        error_code=error_code,
        duration_ms=duration_ms,
        request_truncated=req_trunc,
        response_truncated=resp_trunc,
    )
    db.add(log)
    if commit:
        await db.commit()
    else:
        await db.flush()
    return log


async def record_httpx_exchange(
    db: AsyncSession | None,
    *,
    task_id: str | None,
    tenant_id: str | None,
    run_id: str | None,
    system: str,
    method: str,
    url: str,
    request_body: str | None = None,
    response_or_exc: Any = None,
    status_code: int | None = None,
    error_code: str | None = None,
    duration_ms: int | None = None,
    commit: bool = False,
) -> IntegrationCallLog | None:
    """把一次 httpx 交换（Response 或异常）写成调用日志。缺 db/task 时跳过。"""
    if db is None or not task_id or not tenant_id:
        return None
    resolved_status = status_code
    resolved_body = None
    resolved_error = error_code
    if isinstance(response_or_exc, httpx.Response):
        resolved_status = (
            response_or_exc.status_code if resolved_status is None else resolved_status
        )
        resolved_body = response_or_exc.text or None
    elif isinstance(response_or_exc, BaseException):
        resolved_error = resolved_error or type(response_or_exc).__name__
        resolved_body = f"{type(response_or_exc).__name__}: {response_or_exc}"
    elif isinstance(response_or_exc, str):
        resolved_body = response_or_exc
    elif response_or_exc is not None:
        resolved_body = str(response_or_exc)
    return await record_call(
        db,
        task_id=task_id,
        tenant_id=tenant_id,
        run_id=run_id,
        system=system,
        method=method,
        url=url,
        request_body=request_body,
        response_body=resolved_body,
        status_code=resolved_status,
        error_code=resolved_error,
        duration_ms=duration_ms,
        commit=commit,
    )


async def record_call_by_run(
    db: AsyncSession,
    *,
    run_id: str,
    system: str,
    method: str,
    url: str,
    request_body: str | None = None,
    response_body: str | None = None,
    status_code: int | None = None,
    error_code: str | None = None,
    duration_ms: int | None = None,
    commit: bool = False,
) -> IntegrationCallLog | None:
    """Worker 回调路径：从 run_id 反查 task_id/tenant_id。run 不存在返回 None。"""
    run = (
        await db.execute(
            select(RpaRun).where(RpaRun.id == run_id, not_deleted(RpaRun))
        )
    ).scalar_one_or_none()
    if run is None:
        return None
    # RpaRun 没有 tenant_id，从 task 反查
    from app.models.automation_task import AutomationTask

    task = (
        await db.execute(
            select(AutomationTask).where(
                AutomationTask.id == run.task_id, not_deleted(AutomationTask)
            )
        )
    ).scalar_one_or_none()
    if task is None:
        return None
    return await record_call(
        db,
        task_id=task.id,
        tenant_id=task.tenant_id,
        run_id=run_id,
        system=system,
        method=method,
        url=url,
        request_body=request_body,
        response_body=response_body,
        status_code=status_code,
        error_code=error_code,
        duration_ms=duration_ms,
        commit=commit,
    )


async def list_by_task(
    db: AsyncSession,
    *,
    task_id: str,
    run_id: str | None = None,
) -> list[IntegrationCallLog]:
    """按任务列出调用日志，created_at 升序。可按 run_id 过滤。"""
    query = select(IntegrationCallLog).where(
        IntegrationCallLog.task_id == task_id,
        not_deleted(IntegrationCallLog),
    )
    if run_id:
        query = query.where(IntegrationCallLog.run_id == run_id)
    query = query.order_by(IntegrationCallLog.created_at.asc())
    result = await db.execute(query)
    return list(result.scalars().all())
