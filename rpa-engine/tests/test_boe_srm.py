import pytest

from nodeskclaw_rpa_engine.runtime.boe_srm import login_boe_srm, open_invoice_packing
from nodeskclaw_rpa_engine.runtime.errors import RpaBusinessError, RpaFatalError


class FakeLocator:
    def __init__(self, *, visible: bool = False, name: str = "") -> None:
        self.visible = visible
        self.name = name
        self.fills: list[str] = []
        self.clicks = 0

    @property
    def first(self):
        return self

    async def is_visible(self, timeout=None):  # noqa: ANN001
        return self.visible

    async def fill(self, value: str) -> None:
        self.fills.append(value)

    async def click(self, timeout=None, force=None):  # noqa: ANN001
        self.clicks += 1


class FakePage:
    def __init__(self, locators: dict[str, FakeLocator], *, url: str = "") -> None:
        self._locators = locators
        self.url = url
        self.gotos: list[str] = []

    def locator(self, selector: str) -> FakeLocator:
        return self._locators.get(selector, FakeLocator(name=selector))

    async def goto(self, url, *, wait_until):  # noqa: ANN001
        self.gotos.append(url)
        self.url = url

    async def wait_for_timeout(self, ms):  # noqa: ANN001
        return None


class FakeCtx:
    def __init__(self, page: FakePage, credentials: dict, portal_url: str = "https://supply.boe.com") -> None:
        self.page = page
        self.credentials = credentials
        self.portal_url = portal_url


SELECTORS = {
    "otp_dialog": "otp",
    "username": "user",
    "password": "pass",
    "login_button": "login",
    "nav_delivery": "nav_d",
    "nav_invoice_packing": "nav_p",
}


def sel(name: str) -> str:
    return SELECTORS[name]


@pytest.mark.asyncio
async def test_login_raises_when_otp_visible() -> None:
    page = FakePage(
        {"otp": FakeLocator(visible=True, name="otp")},
        url="https://supply.boe.com/#/dashboard",
    )
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    with pytest.raises(RpaBusinessError) as exc_info:
        await login_boe_srm(ctx, selector=sel)
    assert exc_info.value.code == "BOE_OTP_REQUIRED"


@pytest.mark.asyncio
async def test_login_fills_username_password() -> None:
    user = FakeLocator(name="user")
    password = FakeLocator(name="pass")
    login = FakeLocator(name="login")
    page = FakePage(
        {
            "otp": FakeLocator(visible=False, name="otp"),
            "user": user,
            "pass": password,
            "login": login,
        },
        url="https://supply.boe.com/#/login",
    )
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    await login_boe_srm(ctx, selector=sel)
    assert user.fills == ["AA"]
    assert password.fills == ["secret"]
    assert login.clicks == 1
    assert page.gotos == ["https://supply.boe.com"]


@pytest.mark.asyncio
async def test_open_invoice_packing_rejects_ticket_url() -> None:
    page = FakePage({}, url="https://bsrm.boe.com/page?ticket=abc")
    ctx = FakeCtx(page, {})
    with pytest.raises(RpaFatalError) as exc_info:
        await open_invoice_packing(ctx, selector=sel)
    assert exc_info.value.code == "BOE_TICKET_URL_FORBIDDEN"
