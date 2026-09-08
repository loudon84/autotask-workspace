"""临时：本地完整重放 enrich 1.0.2 flow，抓真实异常堆栈。

用真实会话 storage_state + 真实选择器跑 flow.run()，SSO 免登所以凭证给占位值。
输入用真实实例的 summary（从 service 库读）。

用法：uv run python scripts/_tmp_replay_enrich.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from playwright.async_api import async_playwright


@dataclass(frozen=True, slots=True)
class FrozenCtx:
    """模拟引擎 RunContext（frozen+slots），任何 ctx 属性回写都会炸。"""

    input: Mapping[str, Any]
    credentials: Mapping[str, Any]
    page: Any
    portal_url: str
    selectors: Mapping[str, Any]

ROOT = Path(r"d:\work_space260811\autotask-workspace")
FLOW_DIR = ROOT / "rpa-flows" / "rpa_flow_srm_boe_pack_enrich" / "1.0.2"
SESSION = (
    ROOT / "rpa-engine" / "runtime-cache" / "sessions"
    / "a3668cbaf0893c4e9651e1b67765b8fc19518dfd9c068a83453b51e3adac67f4"
    / "storage_state.json"
)


def load_flow():
    spec = importlib.util.spec_from_file_location("enrich_flow_102", FLOW_DIR / "flow.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


async def main() -> None:
    # 真实输入：从 service 库读最新实例的 summary
    sys.path.insert(0, str(ROOT / "service"))
    import os

    from dotenv import load_dotenv

    load_dotenv(ROOT / "service" / ".env")
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(os.environ["DATABASE_URL"])
    async with eng.connect() as c:
        row = (
            await c.execute(
                text(
                    "SELECT id, biz_key, summary FROM process_instances "
                    "WHERE process_code='srm_boe_invoice_packing' AND deleted_at IS NULL "
                    "ORDER BY updated_at DESC LIMIT 1"
                )
            )
        ).fetchone()
    await eng.dispose()
    instance_id, doc_no, summary = row[0], row[1], row[2]
    if isinstance(summary, str):
        summary = json.loads(summary)
    print("instance:", doc_no, "header.factory:", (summary.get("header") or {}).get("factory"))
    print("lines:", len(summary.get("lines") or []))

    flow = load_flow()
    selectors = json.loads((FLOW_DIR / "selectors.json").read_text(encoding="utf-8"))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(SESSION), accept_downloads=True)
        page = await context.new_page()
        ctx = FrozenCtx(
            page=page,
            portal_url="https://supply.boe.com",
            credentials={"username": "V1002012AA", "password": "placeholder"},
            selectors=selectors,
            input={"instanceId": instance_id, "docNo": doc_no, "summary": summary},
        )
        try:
            result = await flow.run(ctx)
            print("\n=== SUCCESS ===")
            print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
        except Exception:
            print("\n=== FAILED ===")
            traceback.print_exc()
            active = [p for p in context.pages if not p.is_closed()][-1]
            await active.screenshot(path=str(ROOT / "rpa-engine" / "scripts" / "_tmp_replay_fail.png"))
            print("截图: rpa-engine/scripts/_tmp_replay_fail.png, url:", active.url)
        await browser.close()


asyncio.run(main())
