"""Local read-only debug for statement receipt query Flow."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nodeskclaw_rpa_engine.core.config import Settings
from nodeskclaw_rpa_engine.core.logging import configure_logging
from nodeskclaw_rpa_engine.runtime.browser import ManagedBrowserSessionManager
from nodeskclaw_rpa_engine.runtime.engine import RpaRuntime
from nodeskclaw_rpa_engine.runtime.loader import FlowLoader
from nodeskclaw_rpa_engine.workers.schemas import (
    BrowserSessionConfig,
    LeaseRunCommand,
    ResolvedFlowVersion,
    RunCommand,
    RunConfig,
)

from debug_flow_local import ConsoleEventSink, LocalArtifactSink, LocalCredentialResolver, LocalPackageSource

PACKAGE = Path(__file__).resolve().parents[2] / "rpa-flows" / "rpa_flow_srm_stmt_query_receipts" / "1.0.0"


async def main() -> int:
    settings = Settings()
    configure_logging(settings)
    settings.runtime_cleanup_on_finish = True
    username = settings.mock_srm_username.get_secret_value() if settings.mock_srm_username else ""
    password = settings.mock_srm_password.get_secret_value() if settings.mock_srm_password else ""
    if not username or not password:
        print("missing MOCK_SRM credentials")
        return 2
    source = LocalPackageSource(PACKAGE)
    probe_flow = ResolvedFlowVersion(
        flow_version_id=uuid4(),
        rpa_flow_id="rpa_flow_srm_stmt_query_receipts",
        version="1.0.1",
        engine_type="PLAYWRIGHT_CDP",
        package_uri=str(PACKAGE.resolve()),
        package_checksum="",
        package_object_key=None,
        supported_workflow_codes=["srm_stmt_query_receipts"],
        capabilities=[],
    )
    package_bytes = await source.fetch(probe_flow)
    checksum = hashlib.sha256(package_bytes).hexdigest()
    runtime = RpaRuntime(
        settings,
        loader=FlowLoader(settings, source),
        browser_manager=ManagedBrowserSessionManager(),
        artifact_sink=LocalArtifactSink(Path("runtime-cache/debug-artifacts-stmt")),
        event_sink_factory=lambda command: ConsoleEventSink(),
        credential_resolver=LocalCredentialResolver(username, password),
    )
    now = datetime.now(timezone.utc)
    command = RunCommand(
        lease=LeaseRunCommand(
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            lease_id=str(uuid4()),
            workflow_binding_id=str(uuid4()),
            portal_account_id=settings.mock_srm_allowed_portal_account_id or "portal-debug",
            rpa_flow_id="rpa_flow_srm_stmt_query_receipts",
            input={"dateStart": "2026-04-01", "dateEnd": "2026-04-30"},
            tenant_id=settings.mock_srm_allowed_tenant_id or "tenant-debug",
            workflow_template_id=str(uuid4()),
            workflow_code="srm_stmt_query_receipts",
            rpa_engine_type="PLAYWRIGHT_CDP",
            rpa_flow_version="1.0.1",
            credential_ref=settings.mock_srm_credential_ref or "debug",
            config=RunConfig(
                portal_url="http://192.168.102.247:3000",
                browser_session=BrowserSessionConfig(
                    mode="MANAGED",
                    headless=True,
                    channel="chromium",
                    profile_ref=None,
                    cdp_endpoint_ref=None,
                    close_policy="ALWAYS",
                ),
            ),
            lease_expires_at=now + timedelta(minutes=10),
        ),
        flow=ResolvedFlowVersion(
            flow_version_id=uuid4(),
            rpa_flow_id="rpa_flow_srm_stmt_query_receipts",
            version="1.0.1",
            engine_type="PLAYWRIGHT_CDP",
            package_uri=str(PACKAGE.resolve()),
            package_checksum=f"sha256:{checksum}",
            package_object_key=None,
            supported_workflow_codes=["srm_stmt_query_receipts"],
            capabilities=["PLAYWRIGHT_CDP", "BROWSER_SESSION_MANAGED", "SCREENSHOT"],
        ),
    )
    result = await runtime.handle(command)
    print("=== RUN RESULT ===")
    print(json.dumps(result.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2)[:4000])
    return 0 if result.status.value == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
