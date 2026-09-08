"""Category-specific portal fields live in JSONB extra, not new columns."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.portal_category import PortalCategory, parse_portal_category

# @lat: [[design-decisions#Portal Extra Is JSONB]]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class ExtraFieldDescriptor:
    key: str
    label: str
    field_type: str
    required: bool
    placeholder: str = ""
    help_text: str = ""


class PortalExtraError(ValueError):
    """Raised when category extra fails descriptor validation."""


EXTRA_FIELDS_BY_CATEGORY: dict[PortalCategory, tuple[ExtraFieldDescriptor, ...]] = {
    PortalCategory.TIANDI: (),
    PortalCategory.BOE: (
        ExtraFieldDescriptor(
            key="email",
            label="邮箱",
            field_type="email",
            required=True,
            placeholder="该门户客服收验证码的邮箱",
            help_text="验证码邮件的收件人，不是 IMAP 系统邮箱",
        ),
    ),
}


def extra_fields_for(category: str) -> tuple[ExtraFieldDescriptor, ...]:
    parsed = parse_portal_category(category)
    return EXTRA_FIELDS_BY_CATEGORY.get(parsed, ())


def extra_value(portal: object, key: str) -> str:
    extra = getattr(portal, "extra", None)
    if not isinstance(extra, dict):
        return ""
    return str(extra.get(key) or "").strip()


def normalize_portal_extra(*, category: str, extra: dict | None) -> dict[str, str]:
    raw = extra if isinstance(extra, dict) else {}
    out: dict[str, str] = {}
    errors: list[str] = []
    for field in extra_fields_for(category):
        value = str(raw.get(field.key) or "").strip()
        if field.required and not value:
            errors.append(f"{field.label}不能为空")
            continue
        if value and field.field_type == "email" and _EMAIL_RE.fullmatch(value) is None:
            errors.append(f"{field.label}格式不正确")
            continue
        if value:
            out[field.key] = value
    if errors:
        raise PortalExtraError("；".join(errors))
    return out
