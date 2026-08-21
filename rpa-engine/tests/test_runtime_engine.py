from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from nodeskclaw_rpa_engine.core.config import Settings
from nodeskclaw_rpa_engine.flows.manifest import FlowManifest
from nodeskclaw_rpa_engine.runtime.artifacts import ArtifactType
from nodeskclaw_rpa_engine.runtime.engine import RpaRuntime
from nodeskclaw_rpa_engine.runtime.errors import (
    RpaBusinessError,
    RpaHumanRequiredError,
    RpaRetryableError,
)
from nodeskclaw_rpa_engine.runtime.loader import LoadedFlow
from nodeskclaw_rpa_engine.runtime.session_cache import session_cache_key
from nodeskclaw_rpa_engine.workers.schemas import (
    AttemptStatus,
    LeaseRunCommand,
    ResolvedFlowVersion,
    RunCommand,
)


def command(
    *,
    credential_ref: str | None = None,
    dry_run: bool = False,
    credentials: dict[str, str] | None = None,
    extra_config: dict[str, object] | None = None,
) -> RunCommand:
    config: dict[str, object] = {
        "portalUrl": "http://mock.test",
        "dryRun": dry_run,
        "browserSession": {
            "mode": "MANAGED",
            "headless": True,
            "channel": "chromium",
            "profileRef": None,
            "cdpEndpointRef": None,
            "closePolicy": "CLOSE_ON_FINISH",
        },
    }
    if extra_config:
        config.update(extra_config)
    payload: dict[str, object] = {
        "taskId": "task-runtime-1",
        "runId": "run-runtime-1",
        "leaseId": "lease-runtime-1",
        "workflowBindingId": "binding-1",
        "portalAccountId": "portal-1",
        "rpaFlowId": "rpa_flow_runtime_test",
        "input": {"record_id": "record-1"},
        "tenantId": "tenant-1",
        "workflowTemplateId": "template-1",
        "workflowCode": "runtime_test",
        "rpaEngineType": "PLAYWRIGHT_CDP",
        "rpaFlowVersion": "1.0.0",
        "credentialRef": credential_ref,
        "config": config,
        "leaseExpiresAt": (
            datetime.now(UTC) + timedelta(minutes=5)
        ).isoformat(),
    }
    if credentials is not None:
        payload["credentials"] = credentials
    lease = LeaseRunCommand.model_validate(payload)
    return RunCommand(
        lease=lease,
        flow=ResolvedFlowVersion(
            flow_version_id=uuid4(),
            rpa_flow_id="rpa_flow_runtime_test",
            version="1.0.0",
            engine_type="PLAYWRIGHT_CDP",
            package_uri="http://engine/package",
            package_checksum="a" * 64,
            package_object_key="flows/runtime/package.zip",
            supported_workflow_codes=["runtime_test"],
            capabilities=[],
        ),
    )


class FakePage:
    async def screenshot(self, *, path: str, full_page: bool) -> None:
        del full_page
        await asyncio.to_thread(Path(path).write_bytes, b"failure-image")


class FakeSession:
    def __init__(self) -> None:
        self.page = FakePage()
        self.trace_started = False
        self.closed = False
        self.saved_storage_state: Path | None = None

    async def stop_trace(self, _path: Path):
        return None

    async def save_storage_state(self, path: Path) -> None:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(
            path.write_text,
            '{"cookies":[],"origins":[]}',
            encoding="utf-8",
        )
        self.saved_storage_state = path

    async def close(self) -> None:
        self.closed = True


class FakeBrowserManager:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.starts = 0
        self.storage_states: list[Path | None] = []

    async def start(self, *_args, **kwargs):
        self.starts += 1
        self.storage_states.append(kwargs.get("storage_state"))
        return self.session


class FakeLoader:
    def __init__(self, entrypoint) -> None:
        self.entrypoint = entrypoint

    async def load(self, _flow: ResolvedFlowVersion) -> LoadedFlow:
        return LoadedFlow(
            root=Path("."),
            manifest=FlowManifest.model_validate(
                {
                    "rpaFlowId": "rpa_flow_runtime_test",
                    "name": "Runtime Test",
                    "version": "1.0.0",
                    "engineType": "PLAYWRIGHT_CDP",
                    "entrypoint": "flow.py:run",
                    "supportedWorkflowCodes": ["runtime_test"],
                    "inputSchema": [
                        {
                            "name": "record_id",
                            "type": "string",
                            "required": True,
                        }
                    ],
                }
            ),
            selectors={"search": "#search"},
            run=self.entrypoint,
        )


class RecordingArtifactSink:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    async def upload(self, **kwargs) -> str:
        kwargs["content"] = await asyncio.to_thread(kwargs["path"].read_bytes)
        self.items.append(kwargs)
        return f"artifacts/{kwargs['name']}"


class RecordingEventSink:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    async def emit(self, event_type: str, **kwargs) -> None:
        self.items.append({"type": event_type, **kwargs})


def runtime(
    tmp_path,
    entrypoint,
    *,
    credential_resolver=None,
    **settings_updates: object,
):
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "test",
        "runtime_cache_dir": tmp_path / "flows",
        "runtime_work_dir": tmp_path / "runs",
        "runtime_session_cache_dir": tmp_path / "sessions",
        "runtime_trace_mode": "OFF",
        "runtime_retry_backoff_seconds": 0,
        "runtime_cleanup_on_finish": True,
    }
    values.update(settings_updates)
    settings = Settings(**values)
    browser = FakeBrowserManager()
    artifacts = RecordingArtifactSink()
    events = RecordingEventSink()
    handler = RpaRuntime(
        settings,
        loader=FakeLoader(entrypoint),  # type: ignore[arg-type]
        browser_manager=browser,  # type: ignore[arg-type]
        artifact_sink=artifacts,
        event_sink_factory=lambda _command: events,
        credential_resolver=credential_resolver,
    )
    return handler, browser, artifacts, events


async def test_runtime_success_injects_safe_context_and_closes_browser(
    tmp_path,
) -> None:
    observed: dict[str, object] = {}

    async def flow(ctx) -> None:
        observed["input"] = ctx.input["record_id"]
        observed["selector"] = ctx.selectors["search"]
        observed["portal"] = ctx.portal_url
        observed["config"] = dict(ctx.config["browserSession"])
        observed["dryRun"] = ctx.config.get("dryRun")
        observed["searches"] = ctx.config.get("searches")
        await ctx.log.info(
            "safe log",
            {"password": "must-not-leak", "visible": "value"},
        )
        await ctx.events.emit("FLOW_STEP", message="step")

    handler, browser, artifacts, events = runtime(tmp_path, flow)
    result = await handler.handle(
        command(
            dry_run=True,
            extra_config={
                "searches": [
                    {"replyStatus": "待签章"},
                    {"poNo": "POJS2607170008", "treatAsPending": True},
                ]
            },
        )
    )

    assert result.status is AttemptStatus.SUCCESS
    assert observed["input"] == "record-1"
    assert observed["selector"] == "#search"
    assert observed["portal"] == "http://mock.test"
    assert observed["dryRun"] is True
    assert observed["searches"] == [
        {"replyStatus": "待签章"},
        {"poNo": "POJS2607170008", "treatAsPending": True},
    ]
    assert "profileRef" not in observed["config"]
    assert "cdpEndpointRef" not in observed["config"]
    assert browser.session.closed is True
    assert artifacts.items == []
    assert [event["type"] for event in events.items] == [
        "RUNTIME_STARTED",
        "FLOW_LOG",
        "FLOW_STEP",
        "RUNTIME_SUCCEEDED",
    ]
    assert events.items[1]["payload"] == {
        "password": "***",
        "visible": "value",
    }
    assert not (tmp_path / "runs" / "run-runtime-1").exists()


async def test_runtime_retries_retryable_flow_then_succeeds(tmp_path) -> None:
    attempts = 0

    async def flow(_ctx) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RpaRetryableError("PORTAL_TEMPORARY", "Portal is temporarily busy")

    handler, _, _, events = runtime(
        tmp_path,
        flow,
        runtime_max_retries=2,
    )
    result = await handler.handle(command())

    assert result.status is AttemptStatus.SUCCESS
    assert attempts == 3
    assert sum(item["type"] == "RUNTIME_RETRYING" for item in events.items) == 2


async def test_runtime_returns_structured_flow_output(tmp_path) -> None:
    output = {
        "schemaVersion": "ORDER_DOWNLOAD_PUSH_OUTPUT_V1",
        "poNo": "PO-001",
        "lines": [{"lineNumber": "10", "customerItemNumber": "MAT-001"}],
    }

    async def flow(_ctx):
        return output

    handler, _, _, _ = runtime(tmp_path, flow)
    result = await handler.handle(command())

    assert result.status is AttemptStatus.SUCCESS
    assert result.output == output


@pytest.mark.parametrize(
    ("flow_output", "expected_code"),
    [
        (["not-an-object"], "FLOW_OUTPUT_INVALID"),
        ({"value": float("nan")}, "FLOW_OUTPUT_INVALID"),
        ({"nested": {"accessToken": "must-not-pass"}}, "FLOW_OUTPUT_INVALID"),
        ({"payload": "x" * 2048}, "FLOW_OUTPUT_TOO_LARGE"),
    ],
)
async def test_runtime_rejects_invalid_output_without_retry(
    tmp_path,
    flow_output,
    expected_code: str,
) -> None:
    attempts = 0

    async def flow(_ctx):
        nonlocal attempts
        attempts += 1
        return flow_output

    handler, _, _, events = runtime(
        tmp_path,
        flow,
        runtime_max_retries=2,
        runtime_output_max_bytes=1024,
    )
    result = await handler.handle(command())

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == expected_code
    assert result.output is None
    assert attempts == 1
    assert all(item["type"] != "RUNTIME_RETRYING" for item in events.items)


async def test_runtime_maps_human_error_and_captures_failure(tmp_path) -> None:
    async def flow(_ctx) -> None:
        raise RpaHumanRequiredError("MFA_REQUIRED", "Manual verification is required")

    handler, browser, artifacts, events = runtime(tmp_path, flow)
    result = await handler.handle(command())

    assert result.status is AttemptStatus.WAITING_HUMAN
    assert result.error_code == "MFA_REQUIRED"
    assert artifacts.items[0]["artifact_type"] is ArtifactType.SCREENSHOT
    assert artifacts.items[0]["content"] == b"failure-image"
    assert browser.session.closed is True
    assert events.items[-1]["type"] == "RUNTIME_WAITING_HUMAN"


async def test_runtime_maps_business_error_without_retry(tmp_path) -> None:
    attempts = 0

    async def flow(_ctx) -> None:
        nonlocal attempts
        attempts += 1
        raise RpaBusinessError("PO_NOT_FOUND", "Purchase order was not found")

    handler, _, _, _ = runtime(tmp_path, flow, runtime_max_retries=2)
    result = await handler.handle(command())

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == "PO_NOT_FOUND"
    assert attempts == 1


async def test_runtime_rejects_credential_ref_without_resolver(tmp_path) -> None:
    async def flow(_ctx) -> None:
        raise AssertionError("Flow must not execute")

    handler, browser, _, _ = runtime(tmp_path, flow)
    result = await handler.handle(command(credential_ref="secret-ref"))

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == "CREDENTIAL_RESOLVER_UNAVAILABLE"
    assert browser.starts == 0


async def test_runtime_validates_manifest_input_before_browser_start(tmp_path) -> None:
    async def flow(_ctx) -> None:
        raise AssertionError("Flow must not execute")

    handler, browser, _, _ = runtime(tmp_path, flow)
    invalid_command = command()
    invalid_command.lease.input = {}
    result = await handler.handle(invalid_command)

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == "FLOW_INPUT_INVALID"
    assert browser.starts == 0


async def test_runtime_injects_credentials_from_governed_resolver(tmp_path) -> None:
    observed: dict[str, object] = {}

    class Resolver:
        async def resolve(
            self,
            credential_ref,
            *,
            tenant_id,
            portal_account_id,
        ):
            observed["request"] = (
                credential_ref,
                tenant_id,
                portal_account_id,
            )
            return {"username": "demo-user"}

    async def flow(ctx) -> None:
        observed["username"] = ctx.credentials["username"]

    handler, _, _, _ = runtime(
        tmp_path,
        flow,
        credential_resolver=Resolver(),
    )
    result = await handler.handle(command(credential_ref="credential-ref-1"))

    assert result.status is AttemptStatus.SUCCESS
    assert observed["request"] == (
        "credential-ref-1",
        "tenant-1",
        "portal-1",
    )
    assert observed["username"] == "demo-user"


async def test_runtime_uses_lease_credentials_without_resolver(tmp_path) -> None:
    observed: dict[str, object] = {}

    async def flow(ctx) -> None:
        observed["username"] = ctx.credentials["username"]
        observed["password"] = ctx.credentials["password"]
        observed["erpSecret"] = ctx.credentials.get("erpClientSecret")
        observed["config"] = dict(ctx.config)

    handler, _, _, events = runtime(tmp_path, flow)
    result = await handler.handle(
        command(
            credentials={"username": "portal-user", "password": "portal-password"},
            extra_config={
                "erpBaseUrl": "http://erp.example",
                "sdmsBaseUrl": "http://sdms.example",
                "customerName": "客户A",
                "businessEntity": "深圳市芯云信息科技有限公司",
                "ou": "104",
                "erpClientId": "smc_erp",
                "erpClientSecret": "erp-secret",
            },
        )
    )

    assert result.status is AttemptStatus.SUCCESS
    assert observed["username"] == "portal-user"
    assert observed["password"] == "portal-password"
    assert observed["erpSecret"] == "erp-secret"
    assert observed["config"]["erpBaseUrl"] == "http://erp.example"
    assert observed["config"]["customerName"] == "客户A"
    assert observed["config"]["businessEntity"] == "深圳市芯云信息科技有限公司"
    assert observed["config"]["ou"] == "104"
    assert "erpClientSecret" not in observed["config"]
    assert all("erp-secret" not in str(item) for item in events.items)
    assert all("portal-password" not in str(item) for item in events.items)


def test_runtime_work_directory_probe_round_trips_file(tmp_path) -> None:
    run_directory = tmp_path / "runs" / "run-1" / "lease-1"

    RpaRuntime._probe_work_directory(run_directory)

    assert run_directory.is_dir()
    assert list(run_directory.iterdir()) == []


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (PermissionError("work directory denied"), "RUNTIME_WORKDIR_ACCESS_DENIED"),
        (OSError("work directory failed"), "RUNTIME_WORKDIR_WRITE_FAILED"),
    ],
)
async def test_runtime_maps_work_directory_probe_errors(
    tmp_path,
    monkeypatch,
    error: OSError,
    expected_code: str,
) -> None:
    async def flow(_ctx) -> None:
        raise AssertionError("Flow must not execute")

    handler, browser, _, events = runtime(tmp_path, flow)

    def fail_probe(_path: Path) -> None:
        raise error

    monkeypatch.setattr(handler, "_probe_work_directory", fail_probe)

    result = await handler.handle(command())

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == expected_code
    assert browser.starts == 0
    assert events.items[-1]["type"] == "RUNTIME_FAILED"
    assert events.items[-1]["payload"] == {"errorCode": expected_code}


def _portal_command(**kwargs) -> RunCommand:
    return command(
        credentials={"username": "02556", "password": "portal-password"},
        extra_config={"portalUrl": "http://192.168.102.247:3000/#/login"},
        **kwargs,
    )


async def test_runtime_persists_and_restores_portal_session(tmp_path) -> None:
    async def flow(_ctx) -> None:
        return None

    handler, browser, _, _ = runtime(tmp_path, flow)
    first = await handler.handle(_portal_command())

    assert first.status is AttemptStatus.SUCCESS
    assert browser.storage_states == [None]
    saved = browser.session.saved_storage_state
    assert saved is not None
    assert saved.is_file()
    meta = saved.parent / "meta.json"
    assert '"username": "02556"' in meta.read_text(encoding="utf-8")
    assert "portal-password" not in meta.read_text(encoding="utf-8")

    browser.session = FakeSession()
    second = await handler.handle(
        command(
            credentials={"username": "02556", "password": "portal-password"},
            extra_config={"portalUrl": "http://192.168.102.247:3000/"},
        )
    )

    assert second.status is AttemptStatus.SUCCESS
    assert browser.storage_states[1] == saved


async def test_runtime_session_cache_is_isolated_by_login(tmp_path) -> None:
    async def flow(_ctx) -> None:
        return None

    handler, browser, _, _ = runtime(tmp_path, flow)
    await handler.handle(_portal_command())
    browser.session = FakeSession()
    await handler.handle(
        command(
            credentials={"username": "other-login", "password": "portal-password"},
            extra_config={"portalUrl": "http://192.168.102.247:3000/"},
        )
    )

    assert browser.storage_states[0] is None
    assert browser.storage_states[1] is None


async def test_runtime_drops_session_cache_after_login_failure(tmp_path) -> None:
    async def flow(_ctx) -> None:
        raise RpaBusinessError("SRM_LOGIN_FAILED", "Supplier portal login failed")

    key = session_cache_key("http://192.168.102.247:3000", "02556")
    seeded = tmp_path / "sessions" / key / "storage_state.json"
    seeded.parent.mkdir(parents=True)
    seeded.write_text('{"cookies":[{"name":"keep"}],"origins":[]}', encoding="utf-8")

    handler, browser, _, _ = runtime(tmp_path, flow, runtime_max_retries=0)
    result = await handler.handle(_portal_command())

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == "SRM_LOGIN_FAILED"
    assert browser.storage_states == [seeded]
    assert not seeded.exists()


async def test_runtime_keeps_session_cache_when_captcha_fails(tmp_path) -> None:
    async def flow(_ctx) -> None:
        raise RpaRetryableError("CAPTCHA_OCR_FAILED", "captcha failed")

    key = session_cache_key("http://192.168.102.247:3000", "02556")
    seeded = tmp_path / "sessions" / key / "storage_state.json"
    seeded.parent.mkdir(parents=True)
    original = '{"cookies":[{"name":"keep"}],"origins":[]}'
    seeded.write_text(original, encoding="utf-8")

    handler, _, _, _ = runtime(tmp_path, flow, runtime_max_retries=0)
    result = await handler.handle(_portal_command())

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == "CAPTCHA_OCR_FAILED"
    assert seeded.read_text(encoding="utf-8") == original
