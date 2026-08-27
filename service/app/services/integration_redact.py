"""接口调用日志脱敏 + 截断。

写入前处理，日志里不得出现明文密钥：
- Header / JSON 键 / query：password|secret|token|access_token|client_secret|authorization|cookie
- 值替换 [REDACTED]
- URL path 含 oauth/token：响应里的 token 字段必抹（即使用户键名漏网）
- 入参、出参各 1MB，超出截断并置标记
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_BODY_BYTES = 1024 * 1024  # 1MB

# 不区分大小写匹配这些子串的键，值替换 [REDACTED]
_SENSITIVE_KEY_PATTERNS = (
    "password",
    "secret",
    "token",
    "access_token",
    "client_secret",
    "authorization",
    "cookie",
)

_REDACTED = "[REDACTED]"


def _is_sensitive_key(key: str) -> bool:
    lowered = (key or "").lower()
    return any(p in lowered for p in _SENSITIVE_KEY_PATTERNS)


def redact_value(key: str, value: Any) -> Any:
    """按键名决定是否脱敏。oauth/token 响应里的 token 字段强制抹。"""
    if _is_sensitive_key(key):
        return _REDACTED
    return value


def redact_dict(obj: Any, *, force_redact_token: bool = False) -> Any:
    """递归脱敏 dict/list。force_redact_token 用于 oauth/token 响应。"""
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for key, value in obj.items():
            if _is_sensitive_key(str(key)):
                result[key] = _REDACTED
                continue
            if force_redact_token and isinstance(value, str) and "token" in str(key).lower():
                result[key] = _REDACTED
                continue
            result[key] = redact_dict(value, force_redact_token=force_redact_token)
        return result
    if isinstance(obj, list):
        return [redact_dict(item, force_redact_token=force_redact_token) for item in obj]
    return obj


def redact_url(url: str) -> str:
    """抹掉 query 里的敏感值，path 段不动。"""
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


def redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    result: dict[str, str] = {}
    for key, value in headers.items():
        result[key] = _REDACTED if _is_sensitive_key(str(key)) else str(value)
    return result


def _is_oauth_token_url(url: str) -> bool:
    path = (urlsplit(url or "").path or "").lower()
    return "oauth/token" in path


def truncate_body(text: str | None) -> tuple[str | None, bool]:
    """超 1MB 截断并置标记。返回 (body, truncated)。"""
    if text is None:
        return None, False
    if len(text.encode("utf-8")) <= MAX_BODY_BYTES:
        return text, False
    # 按 UTF-8 字节截断，避免截断中间字符
    encoded = text.encode("utf-8")[:MAX_BODY_BYTES]
    truncated = encoded.decode("utf-8", errors="ignore")
    return truncated, True


def normalize_request_body(
    *,
    json_body: Any = None,
    data: dict | None = None,
    content: bytes | str | None = None,
    params: dict | None = None,
    files: Any = None,
    url: str = "",
) -> str | None:
    """把请求体各形式归一为脱敏后的文本。multipart 只记文件名列表不记字节。"""
    # 优先 JSON
    if json_body is not None:
        force_token = _is_oauth_token_url(url)
        redacted = redact_dict(json_body, force_redact_token=force_token)
        return json.dumps(redacted, ensure_ascii=False, default=str)
    # form data
    if data is not None:
        force_token = _is_oauth_token_url(url)
        redacted = {
            str(key): _REDACTED if _is_sensitive_key(str(key)) else str(value)
            for key, value in data.items()
        }
        return json.dumps(redacted, ensure_ascii=False, default=str)
    # 原始 content
    if content is not None:
        if isinstance(content, bytes):
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return f"<{len(content)} bytes binary>"
        return str(content)
    # query params 兜底（httpx params）
    if params:
        redacted = {
            str(key): _REDACTED if _is_sensitive_key(str(key)) else str(value)
            for key, value in params.items()
        }
        return json.dumps(redacted, ensure_ascii=False, default=str)
    # multipart files：只记文件名列表
    if files:
        names: list[str] = []
        if isinstance(files, dict):
            for field, value in files.items():
                _collect_filenames(value, names)
        elif isinstance(files, list):
            for value in files:
                _collect_filenames(value, names)
        return json.dumps({"files": names}, ensure_ascii=False, default=str)
    return None


def _collect_filenames(value: Any, names: list[str]) -> None:
    """从 httpx files 参数提取文件名。"""
    if isinstance(value, tuple):
        # (filename, filelike) 或 (filename, filelike, content_type)
        if value and isinstance(value[0], str):
            names.append(value[0])
        return
    if isinstance(value, str):
        names.append(value)


def normalize_response_body(
    *,
    status_code: int | None,
    response_text: str | None,
    url: str = "",
) -> str | None:
    """出参原文脱敏。JSON 则格式化；非 JSON 原样存。oauth/token 抹 token 字段。"""
    if response_text is None:
        return None
    if not response_text:
        return ""
    force_token = _is_oauth_token_url(url)
    # 尝试 JSON
    try:
        parsed = json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        # 非 JSON，原样（仍尝试抹 query 段已处理 URL，正文不动）
        return response_text
    redacted = redact_dict(parsed, force_redact_token=force_token)
    return json.dumps(redacted, ensure_ascii=False, default=str)


def redact_and_truncate(
    *,
    url: str,
    request_body: str | None,
    response_body: str | None,
) -> tuple[str, str | None, str | None, bool, bool]:
    """对最终文本做截断 + URL/JSON 脱敏。供 record_call 前最后一步。"""
    safe_url = redact_url(url)
    req, req_trunc = truncate_body(normalize_response_body(status_code=None, response_text=request_body, url=url))
    resp, resp_trunc = truncate_body(normalize_response_body(status_code=None, response_text=response_body, url=url))
    return safe_url, req, resp, req_trunc, resp_trunc
