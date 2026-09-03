"""Hardcoded portal customer categories."""

from enum import StrEnum

from app.core.exceptions import BadRequestError


# @lat: [[design-decisions#Portal Category Is Hardcoded]]
class PortalCategory(StrEnum):
    TIANDI = "TIANDI"
    BOE = "BOE"


DEFAULT_PORTAL_CATEGORY = PortalCategory.TIANDI

CATEGORY_LABELS: dict[PortalCategory, str] = {
    PortalCategory.TIANDI: "天地伟业",
    PortalCategory.BOE: "京东方",
}

SCAN_ALLOWED_CATEGORIES = frozenset({PortalCategory.TIANDI})

INVALID_CATEGORY_MESSAGE_KEY = "errors.autotask.portal_account.invalid_category"
SCAN_CATEGORY_UNSUPPORTED_MESSAGE_KEY = "errors.autotask.process.scan_category_unsupported"


def parse_portal_category(
    value: str | None,
    *,
    default_when_missing: bool = True,
) -> PortalCategory:
    text = str(value or "").strip()
    if not text:
        if default_when_missing:
            return DEFAULT_PORTAL_CATEGORY
        raise BadRequestError(
            message="门户分类无效",
            message_key=INVALID_CATEGORY_MESSAGE_KEY,
        )
    try:
        return PortalCategory(text)
    except ValueError:
        raise BadRequestError(
            message="门户分类无效",
            message_key=INVALID_CATEGORY_MESSAGE_KEY,
        ) from None


def category_allows_scan(value: str | None) -> bool:
    try:
        return parse_portal_category(value, default_when_missing=False) in SCAN_ALLOWED_CATEGORIES
    except BadRequestError:
        return False
