from __future__ import annotations

import copy
import json
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from nodeskclaw_rpa_engine.core.logging import redact_sensitive
from nodeskclaw_rpa_engine.runtime.errors import RpaFatalError
from nodeskclaw_rpa_engine.workers.schemas import IntegrationCallCreate

logger = logging.getLogger(__name__)

# 与 service 端 integration_redact 一致的敏感键模式
_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "access_token",
    "client_secret",
    "authorization",
    "cookie",
)
_REDACTED = "[REDACTED]"
_MAX_BODY_BYTES = 1024 * 1024  # 1MB


class RuntimeEventSink(Protocol):
    async def emit(
        self,
        event_type: str,
        *,
        level: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None: ...


class ArtifactApi(Protocol):
    async def screenshot(
        self,
        name: str,
        *,
        full_page: bool = True,
        step_id: str | None = None,
    ) -> Any: ...

    async def save_download(
        self,
        download: Any,
        name: str | None = None,
        *,
        step_id: str | None = None,
    ) -> Any: ...


class CredentialResolver(Protocol):
    async def resolve(
        self,
        credential_ref: str | None,
        *,
        tenant_id: str | None,
        portal_account_id: str | None,
    ) -> Mapping[str, Any]: ...


class DisabledCredentialResolver:
    async def resolve(
        self,
        credential_ref: str | None,
        *,
        tenant_id: str | None,
        portal_account_id: str | None,
    ) -> Mapping[str, Any]:
        del tenant_id, portal_account_id
        if credential_ref is not None:
            raise RpaFatalError(
                "CREDENTIAL_RESOLVER_UNAVAILABLE",
                "Credential resolution is not configured",
            )
        return MappingProxyType({})


class RunLogger:
    def __init__(self, sink: RuntimeEventSink) -> None:
        self._sink = sink

    async def info(
        self,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._sink.emit(
            "FLOW_LOG",
            level="INFO",
            message=str(redact_sensitive(message)),
            payload=self._safe_payload(payload),
        )

    async def warning(
        self,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._sink.emit(
            "FLOW_LOG",
            level="WARNING",
            message=str(redact_sensitive(message)),
            payload=self._safe_payload(payload),
        )

    async def error(
        self,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._sink.emit(
            "FLOW_LOG",
            level="ERROR",
            message=str(redact_sensitive(message)),
            payload=self._safe_payload(payload),
        )

    @staticmethod
    def _safe_payload(
        payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if payload is None:
            return None
        sanitized = redact_sensitive(payload)
        return sanitized if isinstance(sanitized, dict) else {}


class RunEvents:
    def __init__(self, sink: RuntimeEventSink) -> None:
        self._sink = sink

    async def emit(
        self,
        event_type: str,
        *,
        level: str = "INFO",
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._sink.emit(
            event_type,
            level=level,
            message=str(redact_sensitive(message or event_type)),
            payload=RunLogger._safe_payload(payload),
        )


class IntegrationCallSink(Protocol):
    """接口调用日志回调 sink。"""

    async def record(self, request: IntegrationCallCreate) -> None: ...


class TaskIntegrationCallSink:
    """基于 TaskWorkerApiClient 的实现。失败只 warning，不挡业务。"""

    def __init__(self, client: Any, run_id: str) -> None:
        self._client = client
        self._run_id = run_id

    async def record(self, request: IntegrationCallCreate) -> None:
        try:
            await self._client.integration_call(self._run_id, request)
        except Exception:  # noqa: BLE001  回调失败不挡业务
            logger.warning(
                "integration call log failed: %s %s",
                request.method,
                request.url,
            )


class NoopIntegrationCallSink:
    """无 sink 工厂时的占位：不记录，仅放行。"""

    async def record(self, request: IntegrationCallCreate) -> None:
        del request  # 不记录


def _is_sensitive_key(key: str) -> bool:
    lowered = (key or "").lower()
    return any(p in lowered for p in _SENSITIVE_KEY_PARTS)


def _redact_url(url: str) -> str:
    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    redacted_query = [
        (key, _REDACTED if _is_sensitive_key(key) else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(parts._replace(query=urlencode(redacted_query, safe="[]")))


def _redact_dict(obj: Any, *, force_redact_token: bool = False) -> Any:
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for key, value in obj.items():
            if _is_sensitive_key(str(key)):
                result[key] = _REDACTED
                continue
            if force_redact_token and isinstance(value, str) and "token" in str(key).lower():
                result[key] = _REDACTED
                continue
            result[key] = _redact_dict(value, force_redact_token=force_redact_token)
        return result
    if isinstance(obj, list):
        return [_redact_dict(item, force_redact_token=force_redact_token) for item in obj]
    return obj


def _is_oauth_token_url(url: str) -> bool:
    path = (urlsplit(url or "").path or "").lower()
    return "oauth/token" in path


def _truncate(text: str | None) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    if len(text.encode("utf-8")) <= _MAX_BODY_BYTES:
        return text, False
    encoded = text.encode("utf-8")[:_MAX_BODY_BYTES]
    return encoded.decode("utf-8", errors="ignore"), True


def _normalize_request_body(
    *,
    json_body: Any = None,
    data: dict | None = None,
    content: bytes | str | None = None,
    params: dict | None = None,
    files: Any = None,
    url: str = "",
) -> str | None:
    if json_body is not None:
        force_token = _is_oauth_token_url(url)
        redacted = _redact_dict(json_body, force_redact_token=force_token)
        return json.dumps(redacted, ensure_ascii=False, default=str)
    if data is not None:
        force_token = _is_oauth_token_url(url)
        redacted = {
            str(key): _REDACTED if _is_sensitive_key(str(key)) else str(value)
            for key, value in data.items()
        }
        return json.dumps(redacted, ensure_ascii=False, default=str)
    if content is not None:
        if isinstance(content, bytes):
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return f"<{len(content)} bytes binary>"
        return str(content)
    if params:
        redacted = {
            str(key): _REDACTED if _is_sensitive_key(str(key)) else str(value)
            for key, value in params.items()
        }
        return json.dumps(redacted, ensure_ascii=False, default=str)
    if files:
        names: list[str] = []
        if isinstance(files, dict):
            for value in files.values():
                _collect_filenames(value, names)
        elif isinstance(files, list):
            for value in files:
                _collect_filenames(value, names)
        return json.dumps({"files": names}, ensure_ascii=False, default=str)
    return None


def _collect_filenames(value: Any, names: list[str]) -> None:
    if isinstance(value, tuple):
        if value and isinstance(value[0], str):
            names.append(value[0])
        return
    if isinstance(value, str):
        names.append(value)


def _normalize_response_body(
    *,
    response_text: str | None,
    url: str = "",
) -> str | None:
    if response_text is None:
        return None
    if not response_text:
        return ""
    force_token = _is_oauth_token_url(url)
    try:
        parsed = json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        return response_text
    redacted = _redact_dict(parsed, force_redact_token=force_token)
    return json.dumps(redacted, ensure_ascii=False, default=str)


class IntegrationHttp:
    """Flow 主动 HTTP 出口。每次请求（含超时/连接失败）记录一行接口调用日志。

    内部 httpx.AsyncClient(trust_env=False, follow_redirects=False)，与现 Flow 客户端一致。
    记录失败只 warning，不改变返回给 Flow 的 response/异常。
    每次调用通过 system 参数指定归属系统（ERP/SDMS/OA 等）。
    """

    def __init__(
        self,
        *,
        sink: IntegrationCallSink,
        transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._sink = sink
        self._client = httpx.AsyncClient(
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )

    async def get(
        self,
        url: str,
        *,
        system: str = "UNKNOWN",
        params: dict | None = None,
        headers: dict | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request(
            "GET", url, system=system, params=params, headers=headers, **kwargs
        )

    async def post(
        self,
        url: str,
        *,
        system: str = "UNKNOWN",
        json: Any | None = None,
        data: dict | None = None,
        content: bytes | str | None = None,
        files: Any = None,
        headers: dict | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request(
            "POST",
            url,
            system=system,
            json=json,
            data=data,
            content=content,
            files=files,
            headers=headers,
            **kwargs,
        )

    async def request(
        self,
        method: str,
        url: str,
        *,
        system: str = "UNKNOWN",
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request(method, url, system=system, **kwargs)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        system: str = "UNKNOWN",
        **kwargs: Any,
    ) -> httpx.Response:
        start = time.monotonic()
        status_code: int | None = None
        response_text: str | None = None
        error_code: str | None = None
        try:
            response = await self._client.request(method, url, **kwargs)
            status_code = response.status_code
            response_text = response.text if response.text else None
            return response
        except httpx.TimeoutException as exc:
            error_code = "TIMEOUT"
            response_text = f"{type(exc).__name__}: {exc}"
            raise
        except httpx.HTTPError as exc:
            error_code = "NETWORK_ERROR"
            response_text = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._record(
                method=method,
                url=url,
                system=system,
                kwargs=kwargs,
                status_code=status_code,
                response_text=response_text,
                error_code=error_code,
                duration_ms=duration_ms,
            )

    async def _record(
        self,
        *,
        method: str,
        url: str,
        system: str,
        kwargs: Any,
        status_code: int | None,
        response_text: str | None,
        error_code: str | None,
        duration_ms: int,
    ) -> None:
        try:
            request_body = _normalize_request_body(
                json_body=kwargs.get("json"),
                data=kwargs.get("data"),
                content=kwargs.get("content"),
                params=kwargs.get("params"),
                files=kwargs.get("files"),
                url=url,
            )
            response_body = _normalize_response_body(
                response_text=response_text, url=url
            )
            req_text, _ = _truncate(request_body)
            resp_text, _ = _truncate(response_body)
            if isinstance(req_text, str):
                req_text = str(redact_sensitive(req_text))
            if isinstance(resp_text, str):
                resp_text = str(redact_sensitive(resp_text))
            safe_url = redact_sensitive(_redact_url(url))
            await self._sink.record(
                IntegrationCallCreate(
                    system=system,
                    method=method.upper(),
                    url=str(safe_url),
                    request_body=req_text,
                    response_body=resp_text,
                    status_code=status_code,
                    error_code=error_code,
                    duration_ms=duration_ms,
                )
            )
        except Exception:  # noqa: BLE001  记录失败不挡业务
            logger.warning("integration call record failed: %s %s", method, url)

    async def aclose(self) -> None:
        await self._client.aclose()


@dataclass(frozen=True, slots=True)
class RunContext:
    input: Mapping[str, Any]
    credentials: Mapping[str, Any]
    page: Any
    portal_url: str
    selectors: Mapping[str, Any]
    artifacts: ArtifactApi
    log: RunLogger
    events: RunEvents
    config: Mapping[str, Any]
    http: IntegrationHttp

    @classmethod
    def create(
        cls,
        *,
        input_data: Mapping[str, Any],
        credentials: Mapping[str, Any],
        page: Any,
        portal_url: str,
        selectors: Mapping[str, Any],
        artifacts: ArtifactApi,
        event_sink: RuntimeEventSink,
        safe_config: Mapping[str, Any],
        integration_http: IntegrationHttp,
    ) -> RunContext:
        return cls(
            input=MappingProxyType(copy.deepcopy(dict(input_data))),
            credentials=MappingProxyType(copy.deepcopy(dict(credentials))),
            page=page,
            portal_url=portal_url,
            selectors=MappingProxyType(copy.deepcopy(dict(selectors))),
            artifacts=artifacts,
            log=RunLogger(event_sink),
            events=RunEvents(event_sink),
            config=MappingProxyType(copy.deepcopy(dict(safe_config))),
            http=integration_http,
        )
