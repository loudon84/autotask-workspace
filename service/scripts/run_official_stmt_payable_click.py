"""Load official portal credentials and probe 收货应付 clickability. Does not print the password."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.portal_account import PortalAccount

PORTAL_NAME = "天地伟业-国际-正式演练"
ENGINE_PY = Path(r"d:\work_space260811\autotask-workspace\rpa-engine\.venv\Scripts\python.exe")
PROBE = Path(r"d:\work_space260811\autotask-workspace\rpa-engine\scripts\probe_official_stmt_payable_click.py")


async def main() -> int:
    async with async_session_factory() as db:
        portal = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == PORTAL_NAME,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
    await db_engine.dispose()
    if portal is None:
        print("portal_missing")
        return 1
    password = (portal.credential_ref or "").strip()
    if not password:
        print("password_missing")
        return 1
    print("portal", portal.portal_name, "url", portal.portal_url, "user", portal.login_account, flush=True)
    python_exe = str(ENGINE_PY) if ENGINE_PY.is_file() else sys.executable
    env = os.environ.copy()
    env["OFFICIAL_OCR_URL"] = portal.portal_url
    env["OFFICIAL_OCR_USER"] = portal.login_account
    env["OFFICIAL_OCR_PASS"] = password
    env.pop("PLAYWRIGHT_BROWSERS_PATH", None)
    completed = subprocess.run(
        [python_exe, str(PROBE)],
        env=env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
