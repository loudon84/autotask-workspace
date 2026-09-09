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
    def __init__(
        self,
        page: FakePage,
        credentials: dict,
        portal_url: str = "https://supply.boe.com",
        *,
        config: dict | None = None,
        otp=None,  # noqa: ANN001
    ) -> None:
        self.page = page
        self.credentials = credentials
        self.portal_url = portal_url
        self.config = config or {}
        self.otp = otp


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
async def test_login_already_logged_in_ignores_otp_locator() -> None:
    page = FakePage(
        {"otp": FakeLocator(visible=True, name="otp")},
        url="https://supply.boe.com/#/dashboard",
    )
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    await login_boe_srm(ctx, selector=sel)
    assert page.gotos == []


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


class FakeOtp:
    def __init__(self, code: str = "654321") -> None:
        self.code = code
        self.watermarks = 0
        self.fetches = 0

    async def watermark(self) -> int:
        self.watermarks += 1
        return 10

    async def fetch_code(self, **kwargs) -> str:  # noqa: ANN003
        del kwargs
        self.fetches += 1
        return self.code


@pytest.mark.asyncio
async def test_login_otp_without_mailbox_fails() -> None:
    from nodeskclaw_rpa_engine.runtime import boe_srm as mod

    mod._otp_clicks.clear()
    user = FakeLocator(visible=True, name="user")
    get_code = FakeLocator(visible=False, name="get_code")

    def _show_otp() -> None:
        get_code.visible = True

    login = FakeLocator(name="login", on_click=_show_otp)
    page = FakePage(
        {
            "otp": FakeLocator(visible=False, name="otp"),
            "user": user,
            "pass": FakeLocator(name="pass"),
            "privacy": FakeLocator(visible=False, name="privacy"),
            "login": login,
            "#getCodeBtn": get_code,
        },
        url="https://supply.boe.com",
    )
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    with pytest.raises(RpaBusinessError) as exc_info:
        await login_boe_srm(ctx, selector=sel)
    assert exc_info.value.code == "BOE_OTP_MAILBOX_MISSING"


@pytest.mark.asyncio
async def test_login_fills_otp_from_task_client() -> None:
    from nodeskclaw_rpa_engine.runtime import boe_srm as mod

    mod._otp_clicks.clear()
    user = FakeLocator(visible=True, name="user")
    get_code = FakeLocator(visible=False, name="get_code")
    verify = FakeLocator(name="verification")
    home = FakeLocator(visible=False, name="home_menu")
    clicks = {"n": 0}

    def _login_click() -> None:
        clicks["n"] += 1
        if clicks["n"] == 1:
            get_code.visible = True
            return
        user.visible = False
        get_code.visible = False
        home.visible = True

    login = FakeLocator(name="login", on_click=_login_click)
    page = FakePage(
        {
            "otp": FakeLocator(visible=False, name="otp"),
            "user": user,
            "pass": FakeLocator(name="pass"),
            "privacy": FakeLocator(visible=False, name="privacy"),
            "login": login,
            "home_menu": home,
            "#getCodeBtn": get_code,
            "#verificationCode": verify,
            "#emailAuth": FakeLocator(visible=True, name="email_auth"),
        },
        url="https://supply.boe.com",
    )
    otp = FakeOtp()
    ctx = FakeCtx(
        page,
        {"username": "AA", "password": "secret"},
        config={"otpMailbox": "aa@example.com"},
        otp=otp,
    )
    await login_boe_srm(ctx, selector=sel)
    assert otp.watermarks == 1
    assert otp.fetches == 1
    assert verify.fills == ["654321"]
    assert get_code.clicks == 1
    assert home.visible is True


def _otp_page(
    *,
    user: FakeLocator,
    get_code: FakeLocator,
    verify: FakeLocator,
    home: FakeLocator,
    login: FakeLocator,
) -> FakePage:
    return FakePage(
        {
            "otp": FakeLocator(visible=False, name="otp"),
            "user": user,
            "pass": FakeLocator(name="pass"),
            "privacy": FakeLocator(visible=False, name="privacy"),
            "login": login,
            "home_menu": home,
            "#getCodeBtn": get_code,
            "#verificationCode": verify,
            "#emailAuth": FakeLocator(visible=True, name="email_auth"),
        },
        url="https://supply.boe.com",
    )


@pytest.mark.asyncio
async def test_login_otp_bounce_reuses_code_and_retries() -> None:
    """提交验证码后跳回登录页：算一次失败，5 分钟内复用已取码再登，不再点获取验证码。"""
    from nodeskclaw_rpa_engine.runtime import boe_srm as mod

    mod._otp_clicks.clear()
    user = FakeLocator(visible=True, name="user")
    get_code = FakeLocator(visible=False, name="get_code")
    verify = FakeLocator(name="verification")
    home = FakeLocator(visible=False, name="home_menu")
    clicks = {"n": 0}

    def _login_click() -> None:
        clicks["n"] += 1
        if clicks["n"] in (1, 3):
            get_code.visible = True
            return
        if clicks["n"] == 2:
            get_code.visible = False
            return
        user.visible = False
        get_code.visible = False
        home.visible = True

    login = FakeLocator(name="login", on_click=_login_click)
    ctx = FakeCtx(
        _otp_page(
            user=user, get_code=get_code, verify=verify, home=home, login=login
        ),
        {"username": "AA", "password": "secret"},
        config={"otpMailbox": "aa@example.com"},
        otp=FakeOtp(),
    )
    await login_boe_srm(ctx, selector=sel)
    assert ctx.otp.watermarks == 1
    assert ctx.otp.fetches == 1
    assert get_code.clicks == 1
    assert verify.fills == ["654321", "654321"]
    assert user.fills == ["AA", "AA"]
    assert home.visible is True


@pytest.mark.asyncio
async def test_login_otp_bounce_gives_up_after_two_retries() -> None:
    """首次 + 再试 2 次仍跳回登录页则失败；全程只点一次获取验证码。"""
    from nodeskclaw_rpa_engine.runtime import boe_srm as mod

    mod._otp_clicks.clear()
    user = FakeLocator(visible=True, name="user")
    get_code = FakeLocator(visible=False, name="get_code")
    verify = FakeLocator(name="verification")
    home = FakeLocator(visible=False, name="home_menu")
    clicks = {"n": 0}

    def _login_click() -> None:
        clicks["n"] += 1
        if clicks["n"] % 2 == 1:
            get_code.visible = True
            return
        get_code.visible = False

    login = FakeLocator(name="login", on_click=_login_click)
    ctx = FakeCtx(
        _otp_page(
            user=user, get_code=get_code, verify=verify, home=home, login=login
        ),
        {"username": "AA", "password": "secret"},
        config={"otpMailbox": "aa@example.com"},
        otp=FakeOtp(),
    )
    with pytest.raises(RpaBusinessError) as exc_info:
        await login_boe_srm(ctx, selector=sel)
    assert exc_info.value.code == "BOE_LOGIN_FAILED"
    assert "提交验证码后未回到首页" in str(exc_info.value)
    assert ctx.otp.fetches == 1
    assert get_code.clicks == 1
    assert len(verify.fills) == 3
    assert home.visible is False


@pytest.mark.asyncio
async def test_login_password_bounce_retries_without_otp() -> None:
    """点登录又回到账密页、没有验证码区：算一次失败，再填账密登录。"""
    user = FakeLocator(visible=True, name="user")
    home = FakeLocator(visible=False, name="home_menu")
    clicks = {"n": 0}

    def _login_click() -> None:
        clicks["n"] += 1
        if clicks["n"] == 1:
            return
        user.visible = False
        home.visible = True

    login = FakeLocator(name="login", on_click=_login_click)
    page = FakePage(
        {
            "otp": FakeLocator(visible=False, name="otp"),
            "user": user,
            "pass": FakeLocator(name="pass"),
            "privacy": FakeLocator(visible=False, name="privacy"),
            "login": login,
            "home_menu": home,
        },
        url="https://supply.boe.com",
    )
    ctx = FakeCtx(page, {"username": "AA", "password": "secret"})
    await login_boe_srm(ctx, selector=sel)
    assert user.fills == ["AA", "AA"]
    assert login.clicks == 2
    assert home.visible is True
