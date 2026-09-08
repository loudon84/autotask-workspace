import pytest

from nodeskclaw_rpa_engine.runtime.boe_srm import login_boe_srm, open_invoice_packing
from nodeskclaw_rpa_engine.runtime.errors import RpaBusinessError


class FakeLocator:
    def __init__(self, *, visible: bool = False, name: str = "", on_click=None) -> None:  # noqa: ANN001
        self.visible = visible
        self.name = name
        self.on_click = on_click
        self.fills: list[str] = []
        self.clicks = 0
        self.checks = 0

    @property
    def first(self):
        return self

    async def is_visible(self, timeout=None):  # noqa: ANN001
        return self.visible

    async def fill(self, value: str) -> None:
        self.fills.append(value)

    async def click(self, timeout=None, force=None):  # noqa: ANN001
        self.clicks += 1
        if self.on_click:
            self.on_click()

    async def check(self, timeout=None):  # noqa: ANN001
        self.checks += 1

    async def wait_for(self, timeout=None, state=None):  # noqa: ANN001
        if not self.visible:
            raise TimeoutError(f"{self.name} not visible")


class _ExpectPageCM:
    def __init__(self, new_page) -> None:  # noqa: ANN001
        self._new_page = new_page

    async def __aenter__(self):
        if self._new_page is None:
            raise TimeoutError("no new page")
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    @property
    def value(self):  # noqa: ANN201
        async def _get():
            return self._new_page

        return _get()


class FakeContext:
    def __init__(self, new_page=None) -> None:  # noqa: ANN001
        self.new_page = new_page

    def expect_page(self, timeout=None):  # noqa: ANN001
        return _ExpectPageCM(self.new_page)


class FakePage:
    def __init__(
        self,
        locators: dict[str, FakeLocator],
        *,
        url: str = "",
        goto_url: str | None = None,
        new_page=None,  # noqa: ANN001
    ) -> None:
        self._locators = locators
        self.url = url
        self.goto_url = goto_url
        self.gotos: list[str] = []
        self.context = FakeContext(new_page)

    def locator(self, selector: str) -> FakeLocator:
        return self._locators.get(selector, FakeLocator(name=selector))

    async def goto(self, url, *, wait_until):  # noqa: ANN001
        self.gotos.append(url)
        self.url = self.goto_url or url

    async def wait_for_load_state(self, state=None):  # noqa: ANN001
        return None

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
    "privacy_checkbox": "privacy",
    "login_button": "login",
    "supplier_login_entry": "entry",
    "login_success": "home_menu",
    "nav_app_delivery_plan": "app_card",
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
async def test_login_fills_cas_form_with_privacy_checkbox() -> None:
    user = FakeLocator(visible=True, name="user")
    password = FakeLocator(name="pass")
    privacy = FakeLocator(visible=True, name="privacy")

    def _submitted() -> None:
        user.visible = False  # 提交后 CAS 表单消失，回到首页

    login = FakeLocator(name="login", on_click=_submitted)
    page = FakePage(
        {
            "otp": FakeLocator(visible=False, name="otp"),
            "user": user,
            "pass": password,
            "privacy": privacy,
            "login": login,
            "home_menu": FakeLocator(visible=True, name="home_menu"),
        },
        url="https://supply.boe.com",
    )
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    await login_boe_srm(ctx, selector=sel)
    assert user.fills == ["AA"]
    assert password.fills == ["secret"]
    assert privacy.checks == 1
    assert login.clicks == 1
    assert page.gotos == ["https://supply.boe.com"]


@pytest.mark.asyncio
async def test_login_sso_redirect_skips_form() -> None:
    """CAS 有会话时 goto 门户首页会被 SSO 直接跳到 bsrm（带 ticket），不填表单。"""
    user = FakeLocator(name="user")
    page = FakePage(
        {"user": user},
        url="about:blank",
        goto_url="https://bsrm.boe.com/?ticket=ST-1",
    )
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    await login_boe_srm(ctx, selector=sel)
    assert user.fills == []
    assert page.gotos == ["https://supply.boe.com"]


@pytest.mark.asyncio
async def test_login_entry_same_tab_sso_skips_form() -> None:
    """点「供应商登录」同页 SSO 跳 bsrm（带 ticket）：不填表单直接返回。"""
    page = FakePage({}, url="about:blank")

    def _sso() -> None:
        page.url = "https://bsrm.boe.com/?ticket=ST-9"

    entry = FakeLocator(visible=True, name="entry", on_click=_sso)
    user = FakeLocator(name="user")
    page._locators = {"entry": entry, "user": user}
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    await login_boe_srm(ctx, selector=sel)
    assert entry.clicks == 1
    assert user.fills == []


@pytest.mark.asyncio
async def test_login_homepage_already_logged_in() -> None:
    """首页/导航元素已出现 = 已登录，不再点入口、不 goto。"""
    page = FakePage(
        {"home_menu": FakeLocator(visible=True, name="home_menu")},
        url="https://supply.boe.com",
    )
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    await login_boe_srm(ctx, selector=sel)
    assert page.gotos == []


@pytest.mark.asyncio
async def test_login_form_missing_raises() -> None:
    page = FakePage({}, url="about:blank")
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    with pytest.raises(RpaBusinessError) as exc_info:
        await login_boe_srm(ctx, selector=sel)
    assert exc_info.value.code == "BOE_LOGIN_PAGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_open_invoice_packing_allows_ticket_landing() -> None:
    """SSO 落地 bsrm 带 ticket 是正常路径：跳过应用卡；点送货管理展开后点发票箱单。"""
    nav_p = FakeLocator(visible=False, name="nav_p")
    nav_d = FakeLocator(visible=True, name="nav_d", on_click=lambda: setattr(nav_p, "visible", True))
    page = FakePage(
        {"nav_d": nav_d, "nav_p": nav_p},
        url="https://bsrm.boe.com/page?ticket=abc",
    )
    ctx = FakeCtx(page, {})
    page_out = await open_invoice_packing(ctx, selector=sel)
    assert page_out is page
    assert nav_d.clicks == 1
    assert nav_p.clicks == 1


@pytest.mark.asyncio
async def test_open_invoice_packing_menu_reset_retries() -> None:
    """菜单初始化重渲染会把刚点开的子菜单收回去：第一次点无效，重试后展开。"""
    nav_p = FakeLocator(visible=False, name="nav_p")
    state = {"clicks": 0}

    def on_nav_d_click() -> None:
        state["clicks"] += 1
        if state["clicks"] == 1:
            return  # 第一次点开又被菜单初始化收回去
        nav_p.visible = True

    nav_d = FakeLocator(visible=True, name="nav_d", on_click=on_nav_d_click)
    page = FakePage(
        {"nav_d": nav_d, "nav_p": nav_p},
        url="https://bsrm.boe.com/other/#/DeliveryPlan",
    )
    ctx = FakeCtx(page, {})
    await open_invoice_packing(ctx, selector=sel)
    assert nav_d.clicks == 2
    assert nav_p.clicks == 1


@pytest.mark.asyncio
async def test_open_invoice_packing_menu_never_opens() -> None:
    """发票箱单入口一直不可见：报 BOE_NAV_MENU_FAILED。"""
    nav_d = FakeLocator(visible=True, name="nav_d")
    nav_p = FakeLocator(visible=False, name="nav_p")
    page = FakePage(
        {"nav_d": nav_d, "nav_p": nav_p},
        url="https://bsrm.boe.com/other/#/DeliveryPlan",
    )
    ctx = FakeCtx(page, {})
    with pytest.raises(RpaBusinessError) as exc_info:
        await open_invoice_packing(ctx, selector=sel)
    assert exc_info.value.code == "BOE_NAV_MENU_FAILED"
    assert nav_d.clicks == 4
