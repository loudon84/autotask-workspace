"""Local debug harness for running a Flow package through the real RpaRuntime.

Mirrors the production wiring in ``api/app.py`` (FlowLoader +
ManagedBrowserSessionManager + RpaRuntime) but swaps the Task-API-backed
package source, artifact sink, and event sink for local equivalents, so a Flow
package can be executed and debugged end-to-end without the Worker Pool,
Callback Outbox, or a live Task API.

Run it from the repo root with the project venv active::

    .\\.venv\\Scripts\\python.exe scripts\\debug_flow_local.py \\
        --package manifest/rpa_flow_supplier_portal_prepare_erp_order/1.2.3 \\
        --po-no PO12345

Set breakpoints inside ``manifest/.../1.2.3/flow.py`` (e.g. ``run()``) or in the
engine runtime modules and launch this file under the debugger.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Ensure the installed/editable engine package is importable when the script is
# launched directly from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nodeskclaw_rpa_engine.core.config import Settings  # noqa: E402
from nodeskclaw_rpa_engine.core.logging import configure_logging  # noqa: E402
from nodeskclaw_rpa_engine.runtime.artifacts import ArtifactType  # noqa: E402
from nodeskclaw_rpa_engine.runtime.browser import (  # noqa: E402
    ManagedBrowserSessionManager,
)
from nodeskclaw_rpa_engine.runtime.context import (  # noqa: E402
    DisabledCredentialResolver,
    RuntimeEventSink,
)
from nodeskclaw_rpa_engine.runtime.engine import RpaRuntime  # noqa: E402
from nodeskclaw_rpa_engine.runtime.loader import FlowLoader  # noqa: E402
from nodeskclaw_rpa_engine.workers.schemas import (  # noqa: E402
    BrowserSessionConfig,
    LeaseRunCommand,
    ResolvedFlowVersion,
    RunCommand,
    RunConfig,
)

logger = logging.getLogger("debug_flow_local")


# --------------------------------------------------------------------------- #
# Local stand-ins for Task-API-backed dependencies
# --------------------------------------------------------------------------- #
class LocalPackageSource:
    """Serves the Flow ZIP directly from a local directory or .zip file."""

    def __init__(self, package_path: Path) -> None:
        self._package_path = package_path

    async def fetch(self, flow) -> bytes:  # noqa: ANN001
        path = self._package_path
        if path.is_dir():
            buffer = await asyncio.to_thread(self._zip_directory, path)
            return buffer
        return await asyncio.to_thread(path.read_bytes)

    @staticmethod
    def _zip_directory(root: Path) -> bytes:
        import io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(root.rglob("*")):
                if file.is_dir():
                    continue
                if any(part.startswith((".", "__")) for part in file.parts):
                    continue
                archive.write(file, file.relative_to(root).as_posix())
        return buffer.getvalue()


class LocalArtifactSink:
    """Writes artifacts into a local directory instead of the Task API."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir.resolve()

    async def upload(
        self,
        *,
        task_id: str,
        run_id: str,
        artifact_type: ArtifactType,
        name: str,
        path: Path,
        size: int,
        mime_type: str,
    ) -> str:
        del task_id, run_id, size, mime_type
        destination = self._output_dir / artifact_type.value / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, path, destination)
        storage_key = str(destination)
        logger.info("artifact saved: %s (%s)", name, destination)
        return storage_key


class ConsoleEventSink:
    """Prints every runtime/flow event to the console for visibility."""

    async def emit(
        self,
        event_type: str,
        *,
        level: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        line = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
                "event": event_type, "message": message}
        if payload:
            line["payload"] = payload
        print(f"[EVENT] {json.dumps(line, ensure_ascii=False, default=str)}")


class LocalCredentialResolver:
    """Simple username/password resolver backed by env/config, for local debug."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    async def resolve(
        self,
        credential_ref: str | None,
        *,
        tenant_id: str | None,
        portal_account_id: str | None,
    ) -> dict[str, str]:
        del credential_ref, tenant_id, portal_account_id
        if not self._username or not self._password:
            return {}
        return {"username": self._username, "password": self._password}


# --------------------------------------------------------------------------- #
# RunCommand construction
# --------------------------------------------------------------------------- #
def build_command(args: argparse.Namespace, package_checksum: str) -> RunCommand:
    manifest_path = Path(args.package)
    rpa_flow_id = manifest_path.parent.name
    version = manifest_path.name

    browser = BrowserSessionConfig(
        mode="MANAGED",
        headless=args.headless,
        channel=args.channel,
        profile_ref=None,
        cdp_endpoint_ref=None,
        close_policy="ALWAYS",
    )
    config = RunConfig(browser_session=browser, portal_url=args.portal_url)
    lease = LeaseRunCommand(
        task_id=f"debug-task-{uuid4().hex[:8]}",
        run_id=f"debug-run-{uuid4().hex[:8]}",
        lease_id=f"debug-lease-{uuid4().hex[:8]}",
        workflow_binding_id=None,
        portal_account_id=args.portal_account_id,
        rpa_flow_id=rpa_flow_id,
        input={"po_no": args.po_no},
        tenant_id=args.tenant_id,
        workflow_template_id="debug-template",
        workflow_code="srm_prepare_erp_order",
        rpa_engine_type="PLAYWRIGHT_CDP",
        rpa_flow_version=version,
        credential_ref=args.credential_ref,
        config=config,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    flow = ResolvedFlowVersion(
        flow_version_id=uuid4(),
        rpa_flow_id=rpa_flow_id,
        version=version,
        engine_type="PLAYWRIGHT_CDP",
        package_uri=str(Path(args.package).resolve()),
        package_checksum=package_checksum,
        package_object_key=None,
        supported_workflow_codes=["srm_prepare_erp_order"],
        capabilities=[
            "PLAYWRIGHT_CDP",
            "BROWSER_SESSION_MANAGED",
            "SCREENSHOT",
            "DOWNLOAD",
        ],
    )
    return RunCommand(lease=lease, flow=flow)


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package",
        default="manifest/rpa_flow_supplier_portal_prepare_erp_order/1.2.3",
        help="Path to the extracted flow package dir (or a .zip).",
    )
    parser.add_argument("--po-no", required=True, help="Customer PO number input.")
    parser.add_argument(
        "--portal-url",
        default="http://127.0.0.1:4700",
        help="Supplier portal base URL (mock SRM by default).",
    )
    parser.add_argument("--username", default="admin", help="Portal username.")
    parser.add_argument("--password", default="123456", help="Portal password.")
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--portal-account-id", default=None)
    parser.add_argument("--credential-ref", default=None)
    parser.add_argument("--headless", action="store_true", help="Run headless.")
    parser.add_argument(
        "--channel",
        default="chromium",
        choices=["chromium", "chrome", "msedge"],
        help="Browser channel.",
    )
    parser.add_argument(
        "--artifacts",
        default="runtime-cache/debug-artifacts",
        help="Directory for downloaded artifacts/screenshots.",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep the runtime work directory for inspection.",
    )
    args = parser.parse_args()

    package_path = Path(args.package)
    if not package_path.exists():
        logger.error("package not found: %s", package_path)
        return 2

    settings = Settings(log_level="DEBUG")
    settings.runtime_cleanup_on_finish = not args.no_cleanup
    configure_logging(settings)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)

    source = LocalPackageSource(package_path)
    probe_flow = ResolvedFlowVersion(
        flow_version_id=uuid4(),
        rpa_flow_id=package_path.parent.name,
        version=package_path.name,
        engine_type="PLAYWRIGHT_CDP",
        package_uri=str(package_path.resolve()),
        package_checksum="",
        package_object_key=None,
        supported_workflow_codes=[],
        capabilities=[],
    )
    package_bytes = await source.fetch(probe_flow)
    import hashlib

    checksum = hashlib.sha256(package_bytes).hexdigest()

    runtime = RpaRuntime(
        settings,
        loader=FlowLoader(settings, source),
        browser_manager=ManagedBrowserSessionManager(),
        artifact_sink=LocalArtifactSink(Path(args.artifacts)),
        event_sink_factory=lambda command: ConsoleEventSink(),
        credential_resolver=LocalCredentialResolver(args.username, args.password),
    )

    command = build_command(args, checksum)
    logger.info(
        "starting debug run: flow=%s version=%s po_no=%s headless=%s",
        command.flow.rpa_flow_id,
        command.flow.version,
        args.po_no,
        args.headless,
    )
    result = await runtime.handle(command)

    print("\n=== RUN RESULT ===")
    print(
        json.dumps(
            result.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status.value == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
