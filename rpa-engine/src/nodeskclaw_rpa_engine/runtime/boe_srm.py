"""京东方 SRM 登录与发票箱单导航。

邮箱验证码设计见 project-docs/prd/boe/AutoTask-BOE 邮件读取.md。账密提交后
若没有「获取验证码」，当天已免验证码，直接成功、不读邮件。需要码时：选邮箱
→ 拍 IMAP UID 水位 → 点获取验证码 → Task 读信 → 填写提交。提交后若弹回
登录页，算一次失败并再登（最多再试 2 次）；5 分钟内复用已取到的码，不再点
获取验证码。

步骤按影刀实操（project-docs/prd/boe/影刀-京东方-selectorsV2.xml）：
登录 = 门户首页点「供应商登录」（同页跳转）→ CAS 填账号/密码 → 勾选隐私政策
→ 点登录。CAS 有会话时 SSO 免登直接回首页/导航页，不填表单。
登录成功的判定 = 首页/导航页元素出现（或已到 bsrm 域名），不看 ticket。
导航 = 首页点「交货计划管理」应用卡进 bsrm → 送货管理 → 发票箱单。禁止 goto 单据 URL。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from nodeskclaw_rpa_engine.runtime.errors import RpaBusinessError, RpaFatalError

# @lat: [[runtime#BOE SRM login]]

_OTP_FALLBACKS = {
    "otp_dialog": "text=获取验证码",
    "email_auth": "#emailAuth",
    "get_code": "#getCodeBtn",
    "verification_code": "#verificationCode",
    "two_factor": "#twoFactorAuth",
}
_OTP_MAX_CLICKS = 3
_LOGIN_MAX_ATTEMPTS = 3  # 首次 + 再试 2 次
_OTP_TTL_SECONDS = 300
_OTP_WAIT_MS = 90_000
_OTP_POLL_MS = 4_000
_otp_clicks: dict[str, int] = {}


class _OtpCache:
    __slots__ = ("code", "fetched_at")

    def __init__(self, code: str, fetched_at: datetime) -> None:
        self.code = code
        self.fetched_at = fetched_at

    def alive(self, now: datetime | None = None) -> bool:
        moment = now or datetime.now(UTC)
        age = (moment - self.fetched_at).total_seconds()
        return bool(self.code) and age < _OTP_TTL_SECONDS


def _clean(value: Any) -> str:
    return str(value or "").strip()


async def _visible(locator: Any) -> bool:
    try:
        return bool(await locator.first.is_visible())
    except Exception:
        return False


def _otp_sel(selector: Callable[..., str], name: str) -> str:
    try:
        value = selector(name)
        if value:
            return str(value)
    except Exception:
        pass
    return _OTP_FALLBACKS[name]


async def _otp_visible(page: Any, selector: Callable[..., str]) -> bool:
    if await _visible(page.locator(_otp_sel(selector, "get_code"))):
        return True
    if await _visible(page.locator(_otp_sel(selector, "two_factor"))):
        return True
    return await _visible(page.locator(_otp_sel(selector, "otp_dialog")))


def _otp_click_key(username: str) -> str:
    return f"{username}|{date.today().isoformat()}"


def _reserve_otp_click(username: str) -> int:
    key = _otp_click_key(username)
    used = _otp_clicks.get(key, 0) + 1
    _otp_clicks[key] = used
    return used


async def _login_state(page: Any, selector: Callable[..., str]) -> str:
    """登录态判定：已到 bsrm 或首页/导航页元素出现 = 已登录；登录入口或 CAS 表单出现 = 未登录。"""
    if "bsrm.boe.com" in str(getattr(page, "url", "") or ""):
        return "logged_in"
    if "dashboard" in str(getattr(page, "url", "") or ""):
        return "logged_in"
    if await _visible(page.locator(selector("username"))):
        return "form"
    if await _visible(page.locator(selector("supplier_login_entry"))):
        return "entry"
    if await _visible(page.locator(selector("login_success"))):
        return "logged_in"
    return "unknown"


async def _wait_login_state(page: Any, selector: Callable[..., str], rounds: int) -> str:
    state = await _login_state(page, selector)
    for _ in range(rounds):
        if state != "unknown":
            return state
        await page.wait_for_timeout(1000)
        state = await _login_state(page, selector)
    return state


async def _submit_otp_code(
    page: Any, selector: Callable[..., str], code: str
) -> None:
    await page.locator(_otp_sel(selector, "verification_code")).first.fill(code)
    await page.locator(selector("login_button")).first.click()
    await page.wait_for_timeout(2500)


async def _fetch_otp_code(
    ctx: Any, *, selector: Callable[..., str], username: str
) -> _OtpCache:
    page = ctx.page
    otp = ctx.otp
    log = getattr(ctx, "log", None)
    for _attempt in range(_OTP_MAX_CLICKS):
        get_code = page.locator(_otp_sel(selector, "get_code"))
        if not await _visible(get_code):
            break
        used = _reserve_otp_click(username)
        if used > _OTP_MAX_CLICKS:
            raise RpaBusinessError(
                "BOE_OTP_RETRY_EXHAUSTED", "获取验证码次数已用完，停止以免锁号"
            )
        watermark = int(await otp.watermark())
        requested_at = datetime.now(UTC)
        await get_code.first.click()
        if log is not None:
            await log.info("已点击获取验证码")
        waited = 0
        while waited < _OTP_WAIT_MS:
            code = await otp.fetch_code(
                requested_at=requested_at, uid_watermark=watermark
            )
            if code:
                return _OtpCache(str(code), requested_at)
            await page.wait_for_timeout(_OTP_POLL_MS)
            waited += _OTP_POLL_MS
    raise RpaBusinessError("BOE_OTP_TIMEOUT", "未读到本次获取验证码的邮件")


async def _fill_cas_otp(
    ctx: Any,
    *,
    selector: Callable[..., str],
    username: str,
    cache: _OtpCache | None,
) -> _OtpCache:
    page = ctx.page
    config = ctx.config if isinstance(getattr(ctx, "config", None), Mapping) else {}
    mailbox = _clean(config.get("otpMailbox"))
    otp = getattr(ctx, "otp", None)
    if not mailbox:
        raise RpaBusinessError("BOE_OTP_MAILBOX_MISSING", "门户未填客服邮箱，无法读验证码")
    if otp is None:
        raise RpaBusinessError("BOE_OTP_CLIENT_MISSING", "当前引擎未接 Task 读信接口")

    email_auth = page.locator(_otp_sel(selector, "email_auth"))
    if await _visible(email_auth):
        await email_auth.first.click()
        await page.wait_for_timeout(500)

    if cache is None or not cache.alive():
        cache = await _fetch_otp_code(ctx, selector=selector, username=username)
    await _submit_otp_code(page, selector, cache.code)
    return cache


async def _submit_password(
    page: Any, selector: Callable[..., str], username: str, password: str
) -> None:
    await page.locator(selector("username")).first.fill(username)
    await page.locator(selector("password")).first.fill(password)
    privacy = page.locator(selector("privacy_checkbox"))
    if await _visible(privacy):
        try:
            await privacy.first.check(timeout=5000)
        except Exception:
            await privacy.first.click(force=True)
    await page.locator(selector("login_button")).first.click()
    await page.wait_for_timeout(2500)


async def _open_cas_form(
    page: Any, selector: Callable[..., str], portal_url: str, *, reload: bool
) -> str:
    if reload:
        await page.goto(portal_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
    state = await _wait_login_state(page, selector, 5)
    if state == "entry":
        await page.locator(selector("supplier_login_entry")).first.click()
        state = await _wait_login_state(page, selector, 20)
    return state


async def login_boe_srm(ctx: Any, *, selector: Callable[..., str]) -> None:
    page = ctx.page
    credentials = ctx.credentials if isinstance(ctx.credentials, Mapping) else {}
    username = _clean(credentials.get("username"))
    password = str(credentials.get("password", ""))
    if not username or not password:
        raise RpaFatalError("BOE_CREDENTIALS_MISSING", "京东方门户账号或密码缺失")

    state = await _login_state(page, selector)
    if state == "logged_in":
        return

    otp_cache: _OtpCache | None = None
    last_error = "登录后未回到首页/导航页"
    for attempt in range(_LOGIN_MAX_ATTEMPTS):
        state = await _open_cas_form(
            page, selector, ctx.portal_url, reload=attempt == 0 or state == "unknown"
        )
        if state == "logged_in":
            return
        if state != "form":
            last_error = "未找到 CAS 登录表单（#username）"
            continue
        await _submit_password(page, selector, username, password)
        if await _otp_visible(page, selector):
            otp_cache = await _fill_cas_otp(
                ctx, selector=selector, username=username, cache=otp_cache
            )
            state = await _wait_login_state(page, selector, 15)
            if state == "logged_in":
                return
            last_error = "提交验证码后未回到首页/导航页"
            continue
        state = await _wait_login_state(page, selector, 15)
        if state == "logged_in":
            return
        last_error = "登录后未回到首页/导航页"
    if last_error.startswith("未找到"):
        raise RpaBusinessError("BOE_LOGIN_PAGE_NOT_FOUND", last_error)
    raise RpaBusinessError("BOE_LOGIN_FAILED", last_error)


async def open_invoice_packing(ctx: Any, *, selector: Callable[..., str]) -> Any:
    """从导航点击进入，禁止 goto 单据 URL。返回当前活动页（可能换了新标签页）。

    注意：CAS SSO 登录成功后落地 bsrm 会带 ?ticket=ST-xxx，这是正常路径，
    只禁止主动 goto ticket URL，不禁止当前页 URL 含 ticket。
    注意：RunContext 是 frozen dataclass，不能回写 ctx.page；
    调用方必须用返回值继续操作（enrich/save_draft/submit 均已如此）。
    """
    page = ctx.page
    current = str(getattr(page, "url", "") or "")

    if "bsrm.boe.com" not in current:
        # 门户首页点「交货计划管理」应用卡进入 BOE SRM 系统（可能开新标签页）
        card = page.locator(selector("nav_app_delivery_plan")).first
        try:
            async with page.context.expect_page(timeout=8000) as new_page_info:
                await card.click()
            page = await new_page_info.value
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            # 同页跳转：点击已生效，等导航完成
            await page.wait_for_timeout(2500)

    # 侧栏菜单挂载晚于内容区：默认展开「交货计划管理」，初始化完成时会重渲染，
    # 把刚点开的「送货管理」又收回去（实测：点早了新开子菜单 not stable → not visible）。
    # 所以等 1.5s 让菜单初始化完，再按「发票箱单可见吗」决定要不要点，最多 4 轮。
    await page.wait_for_timeout(1500)
    nav_delivery = page.locator(selector("nav_delivery")).first
    nav_packing = page.locator(selector("nav_invoice_packing")).first
    opened = False
    for _ in range(4):
        if await _visible(nav_packing):
            opened = True
            break
        await nav_delivery.click()
        try:
            await nav_packing.wait_for(state="visible", timeout=4000)
        except Exception:
            pass
        await page.wait_for_timeout(500)
    if not opened:
        raise RpaBusinessError(
            "BOE_NAV_MENU_FAILED", "送货管理菜单展开失败：发票箱单入口不可见（已重试 4 轮）"
        )
    await nav_packing.click()
    await page.wait_for_timeout(1200)
    return page


async def prepare_invoice_create(page: Any, *, selector: Callable[..., str], factory: str) -> None:
    """发票箱单新建页前置：关 AI 识别 + 选 BOE 工厂。

    实测（2026-09-07 探针）：新建页默认「启用AI识别=是」，此时全部表单项锁定、
    项目信息「新增」按钮 disabled；点「否」后解锁。未选工厂时点「新增」只会
    toast「请先填写基本信息中的工厂字段」，弹窗不开。工厂通过字段后缀的
    放大镜按钮（button.content-search）唤起「获取工厂」弹窗选择。
    """
    ai_no = page.locator(selector("ai_recognize_no")).first
    if await _visible(ai_no):
        await ai_no.click()
        await page.wait_for_timeout(1500)

    factory = _clean(factory)
    if not factory:
        raise RpaBusinessError(
            "BOE_FACTORY_MISSING", "实例头缺少 BOE 工厂，无法新增项目信息行"
        )
    async def _pick_factory(dialog: Any) -> None:
        await page.locator(selector("factory_code_input")).first.fill(factory)
        await page.locator(selector("factory_search")).first.click()
        await page.wait_for_timeout(2000)
        rows = page.locator(selector("factory_row"))
        count = await rows.count()
        if count < 1:
            raise RpaBusinessError("BOE_FACTORY_NOT_FOUND", f"获取工厂未搜到工厂 {factory}")
        target = rows.first
        for idx in range(count):
            blob = str(await rows.nth(idx).inner_text())
            cells = [c.strip() for c in blob.replace("\t", "\n").split("\n") if c.strip()]
            if cells and cells[0] == factory:
                target = rows.nth(idx)
                break
        await target.click()
        await page.wait_for_timeout(500)
        await page.locator(selector("factory_confirm")).first.click()
        try:
            await dialog.wait_for(state="hidden", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(500)

    async def _factory_value() -> str:
        field = page.locator(selector("factory_input"))
        if not await field.count():
            return ""
        try:
            return str(await field.first.input_value() or "").strip()
        except Exception:
            return ""

    await page.locator(selector("factory_search_button")).first.click()
    dialog = page.locator(selector("factory_dialog")).first
    await dialog.wait_for(state="visible", timeout=10000)
    await _pick_factory(dialog)
    if not await _factory_value():
        # 偶发：行点击未真正选中，确认后工厂字段仍为空 —— 重开弹窗再选一次
        await page.locator(selector("factory_search_button")).first.click()
        await dialog.wait_for(state="visible", timeout=10000)
        await _pick_factory(dialog)
    if not await _factory_value():
        raise RpaBusinessError(
            "BOE_FACTORY_NOT_SET", f"工厂 {factory} 选择后字段仍为空（已重试）"
        )
