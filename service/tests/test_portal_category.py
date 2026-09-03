"""门户分类码写死，名称不进表。"""

import pytest

from app.core.exceptions import BadRequestError
from app.domain.portal_category import (
    DEFAULT_PORTAL_CATEGORY,
    INVALID_CATEGORY_MESSAGE_KEY,
    PortalCategory,
    category_allows_scan,
    parse_portal_category,
)


def test_parse_defaults_when_missing() -> None:
    assert parse_portal_category(None) is DEFAULT_PORTAL_CATEGORY
    assert parse_portal_category("") is PortalCategory.TIANDI
    assert parse_portal_category("  ") is PortalCategory.TIANDI


def test_parse_accepts_known_codes() -> None:
    assert parse_portal_category("TIANDI") is PortalCategory.TIANDI
    assert parse_portal_category("BOE") is PortalCategory.BOE


def test_parse_rejects_unknown_code() -> None:
    with pytest.raises(BadRequestError) as exc_info:
        parse_portal_category("ACME")
    assert exc_info.value.message_key == INVALID_CATEGORY_MESSAGE_KEY


def test_parse_rejects_empty_when_not_defaulting() -> None:
    with pytest.raises(BadRequestError):
        parse_portal_category("", default_when_missing=False)


def test_scan_only_tiandi() -> None:
    assert category_allows_scan("TIANDI") is True
    assert category_allows_scan("BOE") is False
    assert category_allows_scan("ACME") is False
