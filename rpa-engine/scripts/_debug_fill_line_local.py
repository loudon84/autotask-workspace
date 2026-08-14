"""Local debug for fill-line flow 1.0.1 using Engine RpaRuntime."""

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

# reuse helpers from debug_flow_local
from debug_flow_local import (  # type: ignore
    ConsoleEventSink,
    LocalArtifactSink,
    LocalCredentialResolver,
    LocalPackageSource,
)


async def main() -> int:
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"),
    )
    package = Path(__file__).resolve().parents[2] / "rpa-flows" / "rpa_flow_srm_fill_line_delivery_date" / "1.0.2"
    if not package.is_dir():
        package = Path(r"D:\work_space260811\autotask-workspace\rpa-flows\rpa_flow_srm_fill_line_delivery_date\1.0.2")
    portal_url = os.environ.get("SUPPLIER_PORTAL_URL", "http://192.168.102.247:3000").strip()
    username = os.environ.get("SUPPLIER_PORTAL_USERNAME", "").strip()
    password = os.environ.get("SUPPLIER_PORTAL_PASSWORD", "")
    if not username or not password:
        print("missing SUPPLIER_PORTAL_USERNAME/PASSWORD")
        return 2

    settings = Settings(log_level="INFO")
    settings.runtime_cleanup_on_finish = False
    configure_logging(settings)
    source = LocalPackageSource(package)
    probe = ResolvedFlowVersion(
        flow_version_id=uuid4(),
        rpa_flow_id="rpa_flow_srm_fill_line_delivery_date",
        version="1.0.2",
        engine_type="PLAYWRIGHT_CDP",
        package_uri=str(package),
        package_checksum="",
        package_object_key=None,
        supported_workflow_codes=["srm_fill_line_delivery_date"],
        capabilities=["PLAYWRIGHT_CDP", "BROWSER_SESSION_MANAGED", "SCREENSHOT"],
    )
    package_bytes = await source.fetch(probe)
    checksum = hashlib.sha256(package_bytes).hexdigest()

    runtime = RpaRuntime(
        settings,
        loader=FlowLoader(settings, source),
        browser_manager=ManagedBrowserSessionManager(),
        artifact_sink=LocalArtifactSink(Path("runtime-cache/debug-fill-artifacts")),
        event_sink_factory=lambda command: ConsoleEventSink(),
        credential_resolver=LocalCredentialResolver(username, password),
    )
    browser = BrowserSessionConfig(
        mode="MANAGED",
        headless=True,
        channel="chromium",
        profile_ref=None,
        cdp_endpoint_ref=None,
        close_policy="ALWAYS",
    )
    lease = LeaseRunCommand(
        task_id=f"debug-task-{uuid4().hex[:8]}",
        run_id=f"debug-run-{uuid4().hex[:8]}",
        lease_id=f"debug-lease-{uuid4().hex[:8]}",
        workflow_binding_id=None,
        portal_account_id="debug-portal",
        rpa_flow_id="rpa_flow_srm_fill_line_delivery_date",
        input={
            "po_no": "POJS2607180002",
            "line_number": "10",
            "expected_delivery_date": "2026-09-15",
        },
        tenant_id="debug-tenant",
        workflow_template_id="debug-template",
        workflow_code="srm_fill_line_delivery_date",
        rpa_engine_type="PLAYWRIGHT_CDP",
        rpa_flow_version="1.0.1",
        credential_ref="debug",
        config=RunConfig(browser_session=browser, portal_url=portal_url),
        lease_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    flow = ResolvedFlowVersion(
        flow_version_id=uuid4(),
        rpa_flow_id="rpa_flow_srm_fill_line_delivery_date",
        version="1.0.2",
        engine_type="PLAYWRIGHT_CDP",
        package_uri=str(package.resolve()),
        package_checksum=checksum,
        package_object_key=None,
        supported_workflow_codes=["srm_fill_line_delivery_date"],
        capabilities=["PLAYWRIGHT_CDP", "BROWSER_SESSION_MANAGED", "SCREENSHOT"],
    )
    command = RunCommand(lease=lease, flow=flow)
    result = await runtime.handle(command)
    print(json.dumps(result.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2))
    return 0 if result.status.value == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
