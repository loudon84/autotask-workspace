"""SDMS 对账单金额查询（无认证）。"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

SDMS_URL = "http://api.qywx.smart-core.com.cn/sdms/ar_check/view_doc_srm"
CUSTOMER_SITE = "C007193-01_104"  # 天地伟业固定值


def _optional_text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True)
class SdmsCheckLookup:
    amount: Decimal | None
    check_head_id: str | None
    params: dict[str, str]
    error: str | None = None
    check_num: str | None = None


def month_range(today: date) -> tuple[date, date]:
    first = today.replace(day=1)
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    last = nxt - timedelta(days=1)
    return first, last


def _excerpt(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _month_params(today: date) -> dict[str, str]:
    first, last = month_range(today)
    return {
        # SDMS SQL 使用 TO_DATE(..., 'YYYY-MM-DD')，带时间会 ORA-01830
        "create_date_s": f"{first:%Y-%m-%d}",
        "create_date_e": f"{last:%Y-%m-%d}",
        "custom_son_code": CUSTOMER_SITE,
    }


async def fetch_check_amount(today: date | None = None) -> SdmsCheckLookup:
    """查询当月 SDMS 对账总金额。"""
    day = today or date.today()
    params = _month_params(day)
    try:
        # Windows 系统代理会让该接口返回空 502；与 curl 直连不一致，故不读环境/系统代理。
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            resp = await client.get(SDMS_URL, params=params)
            status = resp.status_code
            payload = resp.json()
    except httpx.HTTPError as exc:
        return SdmsCheckLookup(
            None,
            None,
            params,
            error=f"HTTP 调用失败 {type(exc).__name__}: {_excerpt(exc)}",
        )
    except ValueError as exc:
        return SdmsCheckLookup(
            None,
            None,
            params,
            error=f"响应不是 JSON: {_excerpt(exc)}",
        )

    if status >= 400:
        return SdmsCheckLookup(None, None, params, error=f"HTTP {status}")
    if not isinstance(payload, dict):
        return SdmsCheckLookup(None, None, params, error="响应不是对象")
    if payload.get("code") not in (1, "1"):
        return SdmsCheckLookup(
            None,
            None,
            params,
            error=f"code={payload.get('code')} {_excerpt(payload.get('msg'))}",
        )
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return SdmsCheckLookup(None, None, params, error="data 为空")
    row = data[0]
    if not isinstance(row, dict) or row.get("check_amount") is None:
        return SdmsCheckLookup(None, None, params, error="缺少 check_amount")
    try:
        amount = Decimal(str(row["check_amount"]).replace(",", ""))
    except (InvalidOperation, ValueError):
        return SdmsCheckLookup(
            None,
            None,
            params,
            error=f"check_amount 无法解析: {row.get('check_amount')}",
        )
    head_id = row.get("check_head_id")
    return SdmsCheckLookup(
        amount,
        _optional_text(head_id),
        params,
        check_num=_optional_text(row.get("check_num")),
    )


def describe_lookup(lookup: SdmsCheckLookup) -> str:
    query = "&".join(f"{key}={value}" for key, value in lookup.params.items())
    return f"GET {SDMS_URL}?{query}"
