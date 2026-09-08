"""Collect unique BOE SRM logins from portal rows. Do not hardcode AA/AD."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.domain.portal_category import PortalCategory
from app.domain.portal_extra import extra_value
from app.models.enums import PortalAccountStatus

# @lat: [[domain#MailInbox]]


@dataclass(frozen=True)
class BoeSrmLoginTarget:
    login_account: str
    email: str
    sample_portal_id: str


@dataclass(frozen=True)
class BoeSrmLoginCollectResult:
    targets: tuple[BoeSrmLoginTarget, ...]
    errors: tuple[str, ...]


def collect_boe_srm_login_targets(portals: list[Any]) -> BoeSrmLoginCollectResult:
    """Enabled BOE portals → one login per distinct login_account.

    Email comes from the portal row (the CS mailbox). Conflicting emails on the
    same account, or a missing mailbox, become errors instead of guesses.
    """
    groups: dict[str, list[Any]] = defaultdict(list)
    for portal in portals:
        if str(getattr(portal, "category", "") or "") != PortalCategory.BOE.value:
            continue
        if str(getattr(portal, "status", "") or "") != PortalAccountStatus.ENABLED.value:
            continue
        login = str(getattr(portal, "login_account", "") or "").strip()
        if not login:
            continue
        groups[login].append(portal)

    targets: list[BoeSrmLoginTarget] = []
    errors: list[str] = []
    for login in sorted(groups):
        rows = groups[login]
        emails = {
            extra_value(row, "email")
            for row in rows
            if extra_value(row, "email")
        }
        if len(emails) > 1:
            errors.append(
                f"账号 {login} 在多个门户上填了不同邮箱: {', '.join(sorted(emails))}"
            )
            continue
        if not emails:
            errors.append(f"账号 {login} 没有门户填写邮箱")
            continue
        sample = rows[0]
        targets.append(
            BoeSrmLoginTarget(
                login_account=login,
                email=next(iter(emails)),
                sample_portal_id=str(getattr(sample, "id", "") or ""),
            )
        )
    return BoeSrmLoginCollectResult(tuple(targets), tuple(errors))
