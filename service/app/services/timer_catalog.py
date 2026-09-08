"""任务侧登记项。具体任务开发时在此加一项并 register。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TimerRegistration:
    target: str
    name: str
    cron: str
    enabled: bool = False


REGISTRATIONS: tuple[TimerRegistration, ...] = (
    TimerRegistration(
        target="demo.print_now",
        name="打印当前时间",
        cron="0 8 * * *",
        enabled=False,
    ),
    TimerRegistration(
        target="tiandy.scan_pending",
        name="天地伟业-扫单",
        cron="0 8 * * *",
        enabled=False,
    ),
    TimerRegistration(
        target="tiandy.sign_poll",
        name="天地伟业-回签轮询",
        cron="*/30 * * * *",
        enabled=False,
    ),
    TimerRegistration(
        target="boe.pack_match",
        name="京东方-匹配交货计划",
        cron="0 7 * * *",
        enabled=False,
    ),
    TimerRegistration(
        target="boe.srm_login",
        name="京东方-SRM晨间登录",
        cron="0 7 * * *",
        enabled=False,
    ),
)
