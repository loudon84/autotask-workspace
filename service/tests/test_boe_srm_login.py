from types import SimpleNamespace

from app.domain.boe_srm_login import collect_boe_srm_login_targets
from app.domain.portal_extra import PortalExtraError, normalize_portal_extra


def test_normalize_extra_requires_boe_email():
    assert normalize_portal_extra(
        category="BOE", extra={"email": "  cs@example.com "}
    ) == {"email": "cs@example.com"}
    try:
        normalize_portal_extra(category="BOE", extra={})
        raise AssertionError("expected PortalExtraError")
    except PortalExtraError:
        pass
    try:
        normalize_portal_extra(category="BOE", extra={"email": "not-an-email"})
        raise AssertionError("expected PortalExtraError")
    except PortalExtraError:
        pass


def test_normalize_extra_drops_unknown_and_tiandi_keys():
    assert (
        normalize_portal_extra(
            category="TIANDI", extra={"email": "cs@example.com", "foo": "bar"}
        )
        == {}
    )
    assert normalize_portal_extra(
        category="BOE", extra={"email": "cs@example.com", "foo": "bar"}
    ) == {"email": "cs@example.com"}


def _boe(**kwargs):
    defaults = {
        "id": "p",
        "category": "BOE",
        "status": "ENABLED",
        "login_account": "V1002012AA",
        "extra": {"email": "aa@example.com"},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_collect_dedupes_login_account_from_portals():
    result = collect_boe_srm_login_targets(
        [
            _boe(id="p-aa-1"),
            _boe(id="p-aa-2"),
            _boe(
                id="p-ad",
                login_account="V1002012AD",
                extra={"email": "ad@example.com"},
            ),
            _boe(
                id="p-tiandi",
                category="TIANDI",
                login_account="other",
                extra={"email": "ignored@example.com"},
            ),
            _boe(
                id="p-disabled",
                status="DISABLED",
                login_account="V1002012AE",
                extra={"email": "ae@example.com"},
            ),
        ]
    )
    assert [t.login_account for t in result.targets] == [
        "V1002012AA",
        "V1002012AD",
    ]
    assert result.targets[0].email == "aa@example.com"
    assert result.errors == ()


def test_collect_third_account_without_code_change():
    result = collect_boe_srm_login_targets(
        [
            _boe(id="p1"),
            _boe(
                id="p2",
                login_account="V1002012AD",
                extra={"email": "ad@example.com"},
            ),
            _boe(
                id="p3",
                login_account="V1002012AE",
                extra={"email": "ae@example.com"},
            ),
        ]
    )
    assert [t.login_account for t in result.targets] == [
        "V1002012AA",
        "V1002012AD",
        "V1002012AE",
    ]


def test_collect_conflict_and_missing_email():
    result = collect_boe_srm_login_targets(
        [
            _boe(id="p1", extra={"email": "one@example.com"}),
            _boe(id="p2", extra={"email": "two@example.com"}),
            _boe(
                id="p3",
                login_account="V1002012AD",
                extra={},
            ),
        ]
    )
    assert result.targets == ()
    assert len(result.errors) == 2
    assert "不同邮箱" in result.errors[0]
    assert "没有门户填写邮箱" in result.errors[1]
