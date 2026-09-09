"""只登录京东方 SRM，不进发票箱单。晨间定时器与白天补全共用 login_boe_srm。"""

from collections.abc import Mapping

from nodeskclaw_rpa_engine.runtime import RpaBusinessError, login_boe_srm

OUTPUT_SCHEMA = "SRM_BOE_LOGIN_OUTPUT_V1"


def _selector(ctx, name: str) -> str:
    selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}
    value = selectors.get(name)
    if not value:
        raise RpaBusinessError("BOE_SELECTOR_MISSING", f"缺少选择器 {name}")
    return str(value)


async def run(ctx):
    await login_boe_srm(ctx, selector=lambda name: _selector(ctx, name))
    payload = ctx.input if isinstance(ctx.input, Mapping) else {}
    return {
        "schemaVersion": OUTPUT_SCHEMA,
        "loginAccount": payload.get("loginAccount"),
        "loggedIn": True,
    }
