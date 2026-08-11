from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import copy
import io
import json
import os
import re
import shutil
import sys
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any, TextIO
from urllib.parse import quote, quote_plus
from uuid import NAMESPACE_URL, uuid4, uuid5


FLOW_WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = FLOW_WORKSPACE_ROOT.parent
DEFAULT_ENGINE_ROOT = WORKSPACE_ROOT / "nodeskclaw-rpa-engine"
LOCAL_ROOT = FLOW_WORKSPACE_ROOT / ".local"
REQUIRED_FLOW_FILES = ("manifest.json", "selectors.json", "flow.py")


class RunnerConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LocalRunConfiguration:
    portal_url: str
    input_data: dict[str, Any]
    credentials: dict[str, Any]
    browser_session: dict[str, Any]


class InlineCredentialResolver:
    def __init__(self, credentials: Mapping[str, Any]) -> None:
        self._credentials = copy.deepcopy(dict(credentials))

    async def resolve(
        self,
        credential_ref: str | None,
        *,
        tenant_id: str | None,
        portal_account_id: str | None,
    ) -> Mapping[str, Any]:
        del credential_ref, tenant_id, portal_account_id
        return MappingProxyType(copy.deepcopy(self._credentials))


class LocalPackageSource:
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def fetch(self, _flow: Any) -> bytes:
        return self._content


class LocalArtifactSink:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    async def upload(
        self,
        *,
        task_id: str,
        run_id: str,
        artifact_type: Any,
        name: str,
        path: Path,
        size: int,
        mime_type: str,
    ) -> str:
        del task_id, mime_type
        return await asyncio.to_thread(
            self._copy,
            run_id,
            artifact_type,
            name,
            path,
            size,
        )

    def _copy(
        self,
        run_id: str,
        artifact_type: Any,
        name: str,
        path: Path,
        expected_size: int,
    ) -> str:
        type_name = getattr(artifact_type, "value", str(artifact_type))
        destination_dir = (
            self._root / _safe_path_segment(run_id) / _safe_path_segment(type_name)
        ).resolve()
        destination_dir.relative_to(self._root)
        destination_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_filename(name)
        destination = destination_dir / f"{uuid4().hex}-{safe_name}"
        shutil.copyfile(path, destination)
        if destination.stat().st_size != expected_size:
            destination.unlink(missing_ok=True)
            raise OSError("Local Artifact copy size did not match")
        return destination.relative_to(FLOW_WORKSPACE_ROOT).as_posix()


class SafeConsoleEventSink:
    async def emit(
        self,
        event_type: str,
        *,
        level: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        del payload
        print(
            json.dumps(
                {
                    "event": str(event_type),
                    "level": str(level),
                    "message": str(message),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )


class _RedactingTextStream:
    def __init__(self, stream: TextIO, secrets: Iterable[str]) -> None:
        self._stream = stream
        self._secrets = tuple(
            sorted({value for value in secrets if value}, key=len, reverse=True)
        )

    def write(self, value: str) -> int:
        redacted = str(value)
        for secret in self._secrets:
            redacted = redacted.replace(secret, "***")
        self._stream.write(redacted)
        return len(value)

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate an AutoTask Flow version directory locally. "
            "Execution is disabled unless --run is explicitly supplied."
        ),
        epilog=(
            "Example: python tools/local_flow_runner.py "
            "rpa_flow_login_demo/1.0.0 "
            "--config tools/local_flow_config.example.json"
        ),
    )
    parser.add_argument(
        "flow_dir",
        type=Path,
        help="Flow version directory containing manifest.json, selectors.json, flow.py",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Local JSON containing portalUrl, input, credentials, browserSession",
    )
    parser.add_argument(
        "--engine-root",
        type=Path,
        default=Path(os.environ.get("AUTOTASK_RPA_ENGINE_ROOT", DEFAULT_ENGINE_ROOT)),
        help=(
            "RPA Engine repository root "
            "(default: sibling nodeskclaw-rpa-engine repository)"
        ),
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the Flow after validation (browser and external effects possible)",
    )
    return parser


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise RunnerConfigurationError(f"{label} file does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerConfigurationError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RunnerConfigurationError(f"{label} root must be a JSON object")
    return value


def _load_local_configuration(path: Path) -> LocalRunConfiguration:
    value = _read_json_object(path, "Local configuration")
    required = {"portalUrl", "input", "credentials", "browserSession"}
    missing = sorted(required.difference(value))
    unknown = sorted(set(value).difference(required))
    if missing:
        raise RunnerConfigurationError(
            "Local configuration fields are missing: " + ", ".join(missing)
        )
    if unknown:
        raise RunnerConfigurationError(
            "Local configuration fields are unknown: " + ", ".join(unknown)
        )
    portal_url = value["portalUrl"]
    input_data = value["input"]
    credentials = value["credentials"]
    browser_session = value["browserSession"]
    if not isinstance(portal_url, str) or not portal_url.strip():
        raise RunnerConfigurationError("portalUrl must be a non-empty string")
    if not isinstance(input_data, dict):
        raise RunnerConfigurationError("input must be a JSON object")
    if not isinstance(credentials, dict):
        raise RunnerConfigurationError("credentials must be a JSON object")
    if not isinstance(browser_session, dict):
        raise RunnerConfigurationError("browserSession must be a JSON object")
    return LocalRunConfiguration(
        portal_url=portal_url,
        input_data=input_data,
        credentials=credentials,
        browser_session=browser_session,
    )


def _flow_archive(flow_dir: Path) -> bytes:
    if not flow_dir.is_dir():
        raise RunnerConfigurationError(
            f"Flow version directory does not exist: {flow_dir}"
        )
    files: dict[str, bytes] = {}
    for name in REQUIRED_FLOW_FILES:
        path = flow_dir / name
        if not path.is_file():
            raise RunnerConfigurationError(f"Flow file is missing: {path}")
        files[name] = path.read_bytes()

    selectors = json.loads(files["selectors.json"].decode("utf-8"))
    if not isinstance(selectors, dict) or not all(
        isinstance(key, str) for key in selectors
    ):
        raise RunnerConfigurationError("selectors.json must be a JSON object")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in REQUIRED_FLOW_FILES:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, files[name])
    return output.getvalue()


def _engine_api(engine_root: Path) -> SimpleNamespace:
    engine_src = (engine_root.resolve() / "src").resolve()
    if not (engine_src / "nodeskclaw_rpa_engine").is_dir():
        raise RunnerConfigurationError(
            f"RPA Engine source directory is unavailable: {engine_src}"
        )
    engine_src_text = str(engine_src)
    if engine_src_text not in sys.path:
        sys.path.insert(0, engine_src_text)

    from packaging.version import Version

    from nodeskclaw_rpa_engine import __version__
    from nodeskclaw_rpa_engine.core.config import Settings
    from nodeskclaw_rpa_engine.flows.package import (
        FlowPackageValidator,
        PackageLimits,
    )
    from nodeskclaw_rpa_engine.runtime.browser import (
        ManagedBrowserSessionManager,
    )
    from nodeskclaw_rpa_engine.runtime.engine import RpaRuntime
    from nodeskclaw_rpa_engine.runtime.loader import FlowLoader
    from nodeskclaw_rpa_engine.workers.schemas import (
        BrowserSessionConfig,
        LeaseRunCommand,
        ResolvedFlowVersion,
        RunCommand,
    )

    return SimpleNamespace(
        BrowserSessionConfig=BrowserSessionConfig,
        FlowLoader=FlowLoader,
        FlowPackageValidator=FlowPackageValidator,
        LeaseRunCommand=LeaseRunCommand,
        ManagedBrowserSessionManager=ManagedBrowserSessionManager,
        PackageLimits=PackageLimits,
        ResolvedFlowVersion=ResolvedFlowVersion,
        RpaRuntime=RpaRuntime,
        RunCommand=RunCommand,
        Settings=Settings,
        Version=Version,
        engine_version=__version__,
    )


def _settings(api: SimpleNamespace) -> Any:
    return api.Settings(
        _env_file=None,
        app_env="test",
        database_enabled=False,
        minio_enabled=False,
        worker_enabled=False,
        worker_lease_enabled=False,
        runtime_enabled=False,
        runtime_cache_dir=LOCAL_ROOT / "cache",
        runtime_work_dir=LOCAL_ROOT / "runs",
        runtime_cleanup_on_finish=True,
        runtime_trace_mode="ON_FAILURE",
        runtime_max_retries=0,
        runtime_retry_backoff_seconds=0,
        credential_resolver_mode="disabled",
        log_level="WARNING",
    )


def _validate(
    api: SimpleNamespace,
    settings: Any,
    package_bytes: bytes,
    config: LocalRunConfiguration,
) -> tuple[Any, Any, Any]:
    validator = api.FlowPackageValidator(
        api.PackageLimits(
            max_bytes=settings.flow_package_max_bytes,
            max_uncompressed_bytes=settings.flow_package_max_uncompressed_bytes,
            max_files=settings.flow_package_max_files,
            max_compression_ratio=settings.flow_package_max_compression_ratio,
        )
    )
    package = validator.validate("local-flow.zip", package_bytes)
    browser_config = api.BrowserSessionConfig.model_validate(config.browser_session)
    api.ManagedBrowserSessionManager._validate_config(browser_config)
    api.RpaRuntime._validate_input(package.manifest, config.input_data)
    minimum = package.manifest.minimum_engine_version
    if minimum is not None and api.Version(api.engine_version) < api.Version(minimum):
        raise RunnerConfigurationError(
            f"Flow requires Engine {minimum} or newer; local Engine is "
            f"{api.engine_version}"
        )
    flow = api.ResolvedFlowVersion(
        flow_version_id=uuid5(
            NAMESPACE_URL,
            (
                f"local:{package.manifest.rpa_flow_id}:"
                f"{package.manifest.version}:{package.checksum_sha256}"
            ),
        ),
        rpa_flow_id=package.manifest.rpa_flow_id,
        version=package.manifest.version,
        engine_type=package.manifest.engine_type,
        package_uri="local://flow-package",
        package_checksum=package.checksum_sha256,
        package_object_key="local/flow-package.zip",
        supported_workflow_codes=package.manifest.supported_workflow_codes,
        capabilities=package.manifest.capabilities,
    )
    return package, browser_config, flow


def _command(
    api: SimpleNamespace,
    package: Any,
    flow: Any,
    config: LocalRunConfiguration,
) -> Any:
    identity = uuid4().hex
    workflow_code = package.manifest.supported_workflow_codes[0]
    lease = api.LeaseRunCommand.model_validate(
        {
            "taskId": f"local-task-{identity}",
            "runId": f"local-run-{identity}",
            "leaseId": f"local-lease-{identity}",
            "workflowBindingId": "local-binding",
            "portalAccountId": "local-portal",
            "rpaFlowId": package.manifest.rpa_flow_id,
            "input": config.input_data,
            "tenantId": "local-tenant",
            "workflowTemplateId": "local-template",
            "workflowCode": workflow_code,
            "rpaEngineType": package.manifest.engine_type,
            "rpaFlowVersion": package.manifest.version,
            "credentialRef": None,
            "config": {
                "portalUrl": config.portal_url,
                "browserSession": config.browser_session,
            },
            "leaseExpiresAt": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
        }
    )
    return api.RunCommand(lease=lease, flow=flow)


async def _execute(
    api: SimpleNamespace,
    settings: Any,
    package_bytes: bytes,
    config: LocalRunConfiguration,
    command: Any,
) -> Any:
    loader = api.FlowLoader(settings, LocalPackageSource(package_bytes))
    browser_manager = api.ManagedBrowserSessionManager()
    runtime = api.RpaRuntime(
        settings,
        loader=loader,
        browser_manager=browser_manager,
        artifact_sink=LocalArtifactSink(LOCAL_ROOT / "artifacts"),
        event_sink_factory=lambda _command: SafeConsoleEventSink(),
        credential_resolver=InlineCredentialResolver(config.credentials),
    )
    return await runtime.handle(command)


def _safe_path_segment(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    return result[:160] or "local"


def _safe_filename(value: str) -> str:
    leaf = Path(str(value)).name.strip()
    result = re.sub(r"[^A-Za-z0-9._-]+", "_", leaf).strip("._")
    return result[:200] or "artifact"


def _credential_scalar_values(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        values: list[str] = []
        for child in value.values():
            values.extend(_credential_scalar_values(child))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for child in value:
            values.extend(_credential_scalar_values(child))
        return values
    if value is None or isinstance(value, bool):
        return []
    text = str(value)
    return [text] if text else []


def _credential_encodings(credentials: Mapping[str, Any]) -> set[str]:
    raw_values = set(_credential_scalar_values(credentials))
    encodings: set[str] = set(raw_values)
    for value in raw_values:
        encodings.update(
            {
                quote(value, safe=""),
                quote_plus(value, safe=""),
                json.dumps(value, ensure_ascii=False)[1:-1],
            }
        )
    if len(raw_values) <= 20:
        for left in raw_values:
            for right in raw_values:
                encoded = base64.b64encode(f"{left}:{right}".encode()).decode()
                encodings.add(encoded)
    return {value for value in encodings if value}


@contextlib.contextmanager
def _redacted_console(credentials: Mapping[str, Any]) -> Iterable[None]:
    secrets = _credential_encodings(credentials)
    stdout = _RedactingTextStream(sys.stdout, secrets)
    stderr = _RedactingTextStream(sys.stderr, secrets)
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        yield


def _run(args: argparse.Namespace, config: LocalRunConfiguration) -> int:
    api = _engine_api(args.engine_root)
    settings = _settings(api)
    package_bytes = _flow_archive(args.flow_dir.resolve())
    package, _browser_config, flow = _validate(
        api,
        settings,
        package_bytes,
        config,
    )
    command = _command(api, package, flow, config)
    print(
        "Validation passed: "
        f"{package.manifest.rpa_flow_id} {package.manifest.version} "
        f"sha256:{package.checksum_sha256}"
    )
    if not args.run:
        print("Execution skipped. Supply --run to execute the Flow.")
        return 0

    print(
        "Execution enabled. Local Artifacts will be stored under "
        f"{LOCAL_ROOT / 'artifacts'}"
    )
    result = asyncio.run(
        _execute(
            api,
            settings,
            package_bytes,
            config,
            command,
        )
    )
    print(
        json.dumps(
            {
                "status": result.status.value,
                "errorCode": result.error_code,
                "errorMessage": result.error_message,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0 if result.status.value == "SUCCESS" else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = _load_local_configuration(args.config.resolve())
    except Exception as exc:
        print(
            f"Configuration error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    with _redacted_console(config.credentials):
        try:
            return _run(args, config)
        except KeyboardInterrupt:
            print("Execution interrupted.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(
                f"Runner error: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
