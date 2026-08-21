import pytest

from nodeskclaw_rpa_engine.runtime.official_srm_login import (
    _ensure_agreement,
    is_authenticated_portal_url,
    login_official_srm,
)


class FakeLocator:
    def __init__(
        self,
        *,
        count: int = 0,
        classes: str = "",
        clicks: list[str] | None = None,
        name: str = "",
        child_count: int = 0,
        is_checked_raises: bool = False,
    ) -> None:
        self._count = count
        self._classes = classes
        self.clicks = clicks if clicks is not None else []
        self.name = name
        self._child_count = child_count
        self._is_checked_raises = is_checked_raises

    @property
    def first(self):
        return self

    def filter(self, has_text=None):  # noqa: ANN001
        return self

    def locator(self, selector: str):
        return FakeLocator(
            count=self._child_count,
            clicks=self.clicks,
            name=selector,
        )

    async def count(self) -> int:
        return self._count

    async def get_attribute(self, name: str) -> str:
        return self._classes if name == "class" else ""

    async def click(self, timeout=None, force=None):  # noqa: ANN001
        self.clicks.append(self.name or "box")

    async def is_checked(self, timeout=None):  # noqa: ANN001
        if self._is_checked_raises:
            raise TimeoutError("Timeout 30000ms exceeded.")
        return False

    async def check(self, force=None, timeout=None):  # noqa: ANN001
        raise TimeoutError("hidden checkbox")

    async def is_visible(self, timeout=None):  # noqa: ANN001
        return self._count > 0 and "is-checked" not in self._classes

    async def wait_for(self, *, state, timeout):  # noqa: ANN001
        visible = await self.is_visible()
        if state == "visible" and not visible:
            raise TimeoutError(f"Timeout {timeout}ms exceeded.")
        if state == "hidden" and visible:
            raise TimeoutError(f"Timeout {timeout}ms exceeded.")
        return None


class FakePage:
    def __init__(self, locators: dict[str, FakeLocator], *, url: str = "") -> None:
        self._locators = locators
        self.url = url

    def locator(self, selector: str) -> FakeLocator:
        return self._locators.get(selector, FakeLocator(count=0, name=selector))

    async def goto(self, url, *, wait_until):  # noqa: ANN001
        self.url = url

    async def wait_for_timeout(self, milliseconds):  # noqa: ANN001
        return None

    async def fill(self, selector, value):  # noqa: ANN001
        return None

    async def click(self, selector, timeout=None):  # noqa: ANN001
        return None


@pytest.mark.asyncio
async def test_ensure_agreement_clicks_visible_el_checkbox_inner() -> None:
    clicks: list[str] = []
    box = FakeLocator(
        count=1,
        classes="el-checkbox",
        clicks=clicks,
        name="el-checkbox",
        child_count=1,
    )
    page = FakePage(
        {
            ".userAgree .el-checkbox:visible": box,
            ".el-checkbox:visible": FakeLocator(count=0, clicks=clicks),
            "label:has-text('用户注册协议') input[type='checkbox']": FakeLocator(
                count=1,
                is_checked_raises=True,
                clicks=clicks,
                name="hidden-input",
            ),
        }
    )

    def selector(name: str) -> str:
        assert name == "agreement"
        return "label:has-text('用户注册协议') input[type='checkbox']"

    await _ensure_agreement(page, selector)
    assert clicks == [".el-checkbox__inner"]


@pytest.mark.asyncio
async def test_ensure_agreement_skips_already_checked_box() -> None:
    clicks: list[str] = []
    page = FakePage(
        {
            ".userAgree .el-checkbox:visible": FakeLocator(
                count=1,
                classes="el-checkbox is-checked",
                clicks=clicks,
                name="el-checkbox",
            )
        }
    )
    await _ensure_agreement(page, lambda _name: "unused")
    assert clicks == []


def _login_ctx(page: FakePage):
    events: list[str] = []

    class Ctx:
        credentials = {"username": "02556", "password": "secret"}
        portal_url = "https://supplier.tiandy.com"

        class events:
            @staticmethod
            async def emit(event_type, message=None, payload=None):  # noqa: ANN001
                events.append(event_type)

    Ctx.page = page
    return Ctx(), events


def _login_selector(name: str) -> str:
    return {
        "login_success": ".el-menu-item:has-text('订单')",
        "captcha_image": ".el-form-item:has(input[placeholder='验证码']) img:visible",
        "login_error": ".el-message--error",
    }[name]


def test_authenticated_portal_url_accepts_dashboard_and_order_hash() -> None:
    assert is_authenticated_portal_url("https://supplier.tiandy.com/#/dashboard") is True
    assert is_authenticated_portal_url("https://supplier.tiandy.com/#/order/list") is True
    assert is_authenticated_portal_url("https://supplier.tiandy.com/#/home") is True
    assert is_authenticated_portal_url("https://supplier.tiandy.com/#/login") is False
    assert is_authenticated_portal_url("https://supplier.tiandy.com/") is False


@pytest.mark.asyncio
async def test_login_reuses_session_when_dashboard_hash_is_present() -> None:
    ctx, events = _login_ctx(
        FakePage({}, url="https://supplier.tiandy.com/#/dashboard")
    )
    await login_official_srm(ctx, selector=_login_selector)
    assert events == ["STEP_STARTED", "STEP_SUCCEEDED"]


@pytest.mark.asyncio
async def test_login_reuses_session_when_header_order_is_visible() -> None:
    captcha = FakeLocator(count=0, name="captcha")
    page = FakePage(
        {
            ".el-form-item:has(input[placeholder='验证码']) img:visible": captcha,
            ".el-menu-item:has-text('订单')": FakeLocator(count=0),
            "span:has-text('订单')": FakeLocator(count=1, name="header-order"),
        },
        url="https://supplier.tiandy.com/#/",
    )
    original_wait = captcha.wait_for

    async def fail_if_wait(*_a, **_k):  # noqa: ANN001
        raise AssertionError("must not wait for captcha when already logged in")

    captcha.wait_for = fail_if_wait
    ctx, events = _login_ctx(page)
    await login_official_srm(ctx, selector=_login_selector)
    assert events == ["STEP_STARTED", "STEP_SUCCEEDED"]
    captcha.wait_for = original_wait

