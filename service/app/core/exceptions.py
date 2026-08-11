"""Unified exception handling."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class AppException(Exception):
    def __init__(
        self,
        code: int,
        message: str,
        status_code: int = 400,
        message_key: str | None = None,
        error_code: int | None = None,
        message_params: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.error_code = error_code if error_code is not None else code
        self.message = message
        self.message_key = message_key
        self.message_params = message_params
        self.details = details
        self.status_code = status_code


class TaskNotFoundError(AppException):
    def __init__(self, message: str = "Task not found", message_key: str = "autotask.task.not_found"):
        super().__init__(code=40401, message=message, status_code=404, message_key=message_key, error_code=40401)


class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在", message_key: str = "errors.common.not_found"):
        super().__init__(code=40400, message=message, status_code=404, message_key=message_key)


class ForbiddenError(AppException):
    def __init__(self, message: str = "无权限", message_key: str = "errors.common.forbidden"):
        super().__init__(code=40300, message=message, status_code=403, message_key=message_key)


class BadRequestError(AppException):
    def __init__(
        self,
        message: str = "请求参数错误",
        message_key: str = "errors.common.bad_request",
        message_params: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            code=40000,
            message=message,
            status_code=400,
            message_key=message_key,
            message_params=message_params,
            details=details,
        )


class ConflictError(AppException):
    def __init__(
        self,
        message: str = "资源冲突",
        message_key: str = "errors.common.conflict",
        message_params: dict[str, str] | None = None,
    ):
        super().__init__(
            code=40900,
            message=message,
            status_code=409,
            message_key=message_key,
            message_params=message_params,
        )


HTTP_STATUS_DEFAULT_CODES: dict[int, int] = {
    400: 40000,
    401: 40100,
    403: 40300,
    404: 40400,
    409: 40900,
    422: 42200,
    500: 50000,
}


def _normalize_http_detail(detail: Any, status_code: int) -> tuple[int, str, str]:
    default_code = HTTP_STATUS_DEFAULT_CODES.get(status_code, status_code * 100)
    default_key = f"errors.http.status_{status_code}"
    default_message = "请求失败"
    if detail is None:
        return default_code, default_key, default_message

    if isinstance(detail, dict):
        error_code = detail.get("error_code") or detail.get("code") or default_code
        message_key = detail.get("message_key") or default_key
        message = detail.get("message") or detail.get("detail") or default_message
        return int(error_code), str(message_key), str(message)

    if isinstance(detail, str):
        return default_code, default_key, detail

    return default_code, default_key, default_message


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        body: dict[str, Any] = {
            "code": exc.code,
            "error_code": exc.error_code,
            "message_key": exc.message_key,
            "message": exc.message,
            "data": None,
        }
        if exc.message_params:
            body["message_params"] = exc.message_params
        if exc.details:
            body["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        error_code, message_key, message = _normalize_http_detail(exc.detail, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": error_code,
                "error_code": error_code,
                "message_key": message_key,
                "message": message,
                "data": None,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity error: %s", exc)
        message_key = "errors.autotask.portal_account.duplicate"
        if "uq_portal_accounts_tenant_entity_url_login" in str(exc.orig):
            message = "门户账号已存在"
        else:
            message_key = "errors.common.conflict"
            message = "资源冲突"
        return JSONResponse(
            status_code=409,
            content={
                "code": 40900,
                "error_code": 40900,
                "message_key": message_key,
                "message": message,
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={
                "code": 50000,
                "error_code": 50000,
                "message_key": "errors.system.internal_error",
                "message": "服务器内部错误",
                "data": None,
            },
        )
