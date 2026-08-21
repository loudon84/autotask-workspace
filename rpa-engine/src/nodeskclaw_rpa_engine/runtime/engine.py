from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from nodeskclaw_rpa_engine.core.config import RuntimeTraceMode, Settings
from nodeskclaw_rpa_engine.core.logging import bind_log_context
from nodeskclaw_rpa_engine.flows.manifest import FlowManifest
from nodeskclaw_rpa_engine.runtime.artifacts import (
    ArtifactRecorder,
    ArtifactSink,
    ArtifactType,
)
from nodeskclaw_rpa_engine.runtime.browser import (
    BrowserSession,
    ManagedBrowserSessionManager,
)
from nodeskclaw_rpa_engine.runtime.context import (
    CredentialResolver,
    DisabledCredentialResolver,
    RunContext,
    RuntimeEventSink,
)
from nodeskclaw_rpa_engine.runtime.errors import (
    ErrorDecision,
    ErrorHandler,
    RpaBusinessError,
    RpaFatalError,
    RpaRuntimeError,
)
from nodeskclaw_rpa_engine.runtime.loader import FlowLoader
from nodeskclaw_rpa_engine.runtime.session_cache import (
    PortalSessionCache,
    session_cache_key,
    should_drop_session,
    should_persist_session,
)
from nodeskclaw_rpa_engine.workers.schemas import (
    AttemptStatus,
    LeaseRunCommand,
    RunCommand,
    RunResult,
)

logger = logging.getLogger(__name__)

EventSinkFactory = Callable[[RunCommand], RuntimeEventSink]
_SENSITIVE_OUTPUT_KEY_PARTS = (
    "authorization",
    "credential",
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
)


@dataclass(frozen=True, slots=True)
class _FlowExecution:
    decision: ErrorDecision | None
    output: dict[str, Any] | None = None


class RpaRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        loader: FlowLoader,
        browser_manager: ManagedBrowserSessionManager,
        artifact_sink: ArtifactSink,
        event_sink_factory: EventSinkFactory,
        credential_resolver: CredentialResolver | None = None,
        error_handler: ErrorHandler | None = None,
    ) -> None:
        self._settings = settings
        self._loader = loader
        self._browser_manager = browser_manager
        self._artifact_sink = artifact_sink
        self._event_sink_factory = event_sink_factory
        self._credential_resolver = (
            credential_resolver or DisabledCredentialResolver()
        )
        self._error_handler = error_handler or ErrorHandler()
        self._work_root = settings.runtime_work_dir.resolve()
        self._session_cache = PortalSessionCache(
            settings.runtime_session_cache_dir.resolve()
        )

    async def handle(self, command: RunCommand) -> RunResult:
        lease = command.lease
        sink = self._event_sink_factory(command)
        run_directory = self._run_directory(lease.run_id, lease.lease_id)
        session: BrowserSession | None = None
        recorder: ArtifactRecorder | None = None
        trace_recorded = False
        cache_key: str | None = None
        cache_username = ""
        outcome_error_code: str | None = None
        with bind_log_context(
            run_id=lease.run_id,
            worker_id=self._settings.worker_id,
            flow_version_id=str(command.flow.flow_version_id),
        ):
            await self._emit(
                sink,
                "RUNTIME_STARTED",
                message="Runtime started",
                payload={"flowVersionId": str(command.flow.flow_version_id)},
            )
            try:
                await self._verify_work_directory(run_directory)
                loaded = await self._loader.load(command.flow)
                self._validate_input(loaded.manifest, lease.input)
                credentials = self._portal_credentials(lease)
                if credentials is None:
                    credentials = dict(
                        await self._credential_resolver.resolve(
                            lease.credential_ref,
                            tenant_id=lease.tenant_id,
                            portal_account_id=lease.portal_account_id,
                        )
                    )
                credentials = self._merge_erp_credentials(lease, credentials)
                identity = self._session_identity(
                    credentials,
                    lease.config.portal_url,
                )
                if identity is not None:
                    cache_key, cache_username = identity
                trace_enabled = (
                    self._settings.runtime_trace_mode is not RuntimeTraceMode.OFF
                )
                async with self._session_cache.lock(cache_key):
                    try:
                        session = await self._browser_manager.start(
                            lease.config.browser_session,
                            run_directory=run_directory,
                            trace_enabled=trace_enabled,
                            storage_state=self._session_cache.existing_state_path(
                                cache_key
                            ),
                        )
                        recorder = ArtifactRecorder(
                            page=session.page,
                            task_id=lease.task_id,
                            run_id=lease.run_id,
                            run_directory=run_directory,
                            sink=self._artifact_sink,
                            max_bytes=self._settings.artifact_max_bytes,
                        )
                        context = RunContext.create(
                            input_data=lease.input,
                            credentials=credentials,
                            page=session.page,
                            portal_url=lease.config.portal_url,
                            selectors=loaded.selectors,
                            artifacts=recorder,
                            event_sink=sink,
                            safe_config=self._safe_config(command),
                        )
                        execution = await self._execute_with_retries(
                            loaded.run,
                            context,
                            sink,
                        )
                        if execution.decision is None:
                            if (
                                self._settings.runtime_trace_mode
                                is RuntimeTraceMode.ALWAYS
                            ):
                                trace_recorded = await self._record_trace(
                                    session,
                                    recorder,
                                    run_directory,
                                )
                            await self._emit(
                                sink,
                                "RUNTIME_SUCCEEDED",
                                message="Runtime completed successfully",
                            )
                            return RunResult(
                                status=AttemptStatus.SUCCESS,
                                output=execution.output,
                            )

                        result = execution.decision
                        outcome_error_code = result.error_code
                        await self._capture_failure(recorder)
                        if self._settings.runtime_trace_mode in {
                            RuntimeTraceMode.ALWAYS,
                            RuntimeTraceMode.ON_FAILURE,
                        }:
                            trace_recorded = await self._record_trace(
                                session,
                                recorder,
                                run_directory,
                            )
                        await self._emit(
                            sink,
                            "RUNTIME_WAITING_HUMAN"
                            if result.status is AttemptStatus.WAITING_HUMAN
                            else "RUNTIME_FAILED",
                            level=(
                                "WARNING"
                                if result.status is AttemptStatus.WAITING_HUMAN
                                else "ERROR"
                            ),
                            message=result.error_message,
                            payload={"errorCode": result.error_code},
                        )
                        return RunResult(
                            status=result.status,
                            error_code=result.error_code,
                            error_message=result.error_message,
                        )
                    except Exception as exc:
                        decision = self._error_handler.classify(
                            exc,
                            attempt_no=self._settings.runtime_max_retries + 1,
                            max_retries=self._settings.runtime_max_retries,
                        )
                        outcome_error_code = decision.error_code
                        if recorder is not None:
                            await self._capture_failure(recorder)
                        if (
                            session is not None
                            and recorder is not None
                            and self._settings.runtime_trace_mode
                            in {
                                RuntimeTraceMode.ALWAYS,
                                RuntimeTraceMode.ON_FAILURE,
                            }
                        ):
                            trace_recorded = await self._record_trace(
                                session,
                                recorder,
                                run_directory,
                            )
                        await self._emit(
                            sink,
                            "RUNTIME_FAILED",
                            level="ERROR",
                            message=decision.error_message,
                            payload={"errorCode": decision.error_code},
                        )
                        return RunResult(
                            status=decision.status,
                            error_code=decision.error_code,
                            error_message=decision.error_message,
                        )
                    finally:
                        if session is not None:
                            if session.trace_started and not trace_recorded:
                                with contextlib.suppress(Exception):
                                    await session.stop_trace(
                                        run_directory / "trace-discard.zip"
                                    )
                            await self._finish_session_cache(
                                cache_key,
                                cache_username,
                                lease.config.portal_url,
                                session,
                                self._resolved_session_error_code(outcome_error_code),
                            )
                            await session.close()
            except Exception as exc:
                decision = self._error_handler.classify(
                    exc,
                    attempt_no=self._settings.runtime_max_retries + 1,
                    max_retries=self._settings.runtime_max_retries,
                )
                if recorder is not None:
                    await self._capture_failure(recorder)
                if (
                    session is not None
                    and recorder is not None
                    and self._settings.runtime_trace_mode
                    in {RuntimeTraceMode.ALWAYS, RuntimeTraceMode.ON_FAILURE}
                ):
                    trace_recorded = await self._record_trace(
                        session,
                        recorder,
                        run_directory,
                    )
                await self._emit(
                    sink,
                    "RUNTIME_FAILED",
                    level="ERROR",
                    message=decision.error_message,
                    payload={"errorCode": decision.error_code},
                )
                return RunResult(
                    status=decision.status,
                    error_code=decision.error_code,
                    error_message=decision.error_message,
                )
            finally:
                if self._settings.runtime_cleanup_on_finish:
                    await asyncio.to_thread(self._cleanup, run_directory)

    def _session_identity(
        self,
        credentials: Mapping[str, Any],
        portal_url: str,
    ) -> tuple[str, str] | None:
        if not self._settings.runtime_session_cache_enabled:
            return None
        username = str(credentials.get("username") or "").strip()
        if not username:
            return None
        return session_cache_key(portal_url, username), username

    @staticmethod
    def _resolved_session_error_code(outcome: str | None) -> str | None:
        if outcome is not None:
            return outcome
        pending = sys.exc_info()[1]
        if isinstance(pending, RpaRuntimeError):
            return pending.code
        return None

    async def _finish_session_cache(
        self,
        cache_key: str | None,
        username: str,
        portal_url: str,
        session: BrowserSession,
        error_code: str | None,
    ) -> None:
        if not cache_key:
            return
        try:
            if should_drop_session(error_code):
                await asyncio.to_thread(self._session_cache.drop, cache_key)
                return
            if not should_persist_session(error_code):
                return
            await self._session_cache.persist(
                cache_key,
                session,
                portal_url=portal_url,
                username=username,
            )
        except Exception:
            logger.warning(
                "Portal session cache update failed",
                extra={"sessionCacheKey": cache_key[:12]},
            )

    async def _execute_with_retries(
        self,
        entrypoint: Callable[[RunContext], Any],
        context: RunContext,
        sink: RuntimeEventSink,
    ) -> _FlowExecution:
        attempt_no = 0
        while True:
            attempt_no += 1
            try:
                raw_output = await asyncio.wait_for(
                    entrypoint(context),
                    timeout=self._settings.runtime_timeout_seconds,
                )
                return _FlowExecution(
                    decision=None,
                    output=self._validate_output(raw_output),
                )
            except Exception as exc:
                decision = self._error_handler.classify(
                    exc,
                    attempt_no=attempt_no,
                    max_retries=self._settings.runtime_max_retries,
                )
                if not decision.retry:
                    return _FlowExecution(decision=decision)
                await self._emit(
                    sink,
                    "RUNTIME_RETRYING",
                    level="WARNING",
                    message="Retrying Flow execution",
                    payload={
                        "attemptNo": attempt_no,
                        "errorCode": decision.error_code,
                    },
                )
                if self._settings.runtime_retry_backoff_seconds > 0:
                    await asyncio.sleep(
                        self._settings.runtime_retry_backoff_seconds
                    )

    def _validate_output(self, value: object) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise RpaFatalError(
                "FLOW_OUTPUT_INVALID",
                "Flow output must be a JSON object or null",
            )
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (OverflowError, RecursionError, TypeError, ValueError) as exc:
            raise RpaFatalError(
                "FLOW_OUTPUT_INVALID",
                "Flow output is not valid JSON",
            ) from exc
        self._validate_output_keys(value)
        if len(encoded) > self._settings.runtime_output_max_bytes:
            raise RpaFatalError(
                "FLOW_OUTPUT_TOO_LARGE",
                "Flow output exceeds the configured size limit",
            )
        return value

    @classmethod
    def _validate_output_keys(cls, value: object) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise RpaFatalError(
                        "FLOW_OUTPUT_INVALID",
                        "Flow output object keys must be strings",
                    )
                normalized = re.sub(r"[^a-z0-9]+", "", key.casefold())
                if any(part in normalized for part in _SENSITIVE_OUTPUT_KEY_PARTS):
                    raise RpaFatalError(
                        "FLOW_OUTPUT_INVALID",
                        "Flow output contains a prohibited sensitive field",
                    )
                cls._validate_output_keys(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                cls._validate_output_keys(child)

    async def _record_trace(
        self,
        session: BrowserSession,
        recorder: ArtifactRecorder,
        run_directory: Path,
    ) -> bool:
        try:
            trace = await session.stop_trace(run_directory / "traces" / "trace.zip")
            if trace is None:
                return False
            await recorder.record_file(
                trace,
                artifact_type=ArtifactType.TRACE,
                name="trace.zip",
                mime_type="application/zip",
            )
            return True
        except Exception:
            logger.warning("Runtime trace recording failed")
            return False

    @staticmethod
    async def _capture_failure(recorder: ArtifactRecorder) -> None:
        with contextlib.suppress(Exception):
            await recorder.screenshot("failure", full_page=True)

    @staticmethod
    async def _emit(
        sink: RuntimeEventSink,
        event_type: str,
        *,
        level: str = "INFO",
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        try:
            await sink.emit(
                event_type,
                level=level,
                message=message,
                payload=payload,
            )
        except Exception:
            logger.warning(
                "Runtime event sink failed",
                extra={"eventType": event_type},
            )

    @staticmethod
    def _portal_credentials(lease: LeaseRunCommand) -> dict[str, Any] | None:
        creds = lease.credentials
        if creds is None:
            return None
        username = str(creds.username or "").strip()
        password = str(creds.password or "")
        if username and password:
            return {"username": username, "password": password}
        return None

    @staticmethod
    def _merge_erp_credentials(
        lease: LeaseRunCommand,
        credentials: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = dict(credentials)
        config = lease.config
        client_id = str(getattr(config, "erp_client_id", "") or "").strip()
        client_secret = str(getattr(config, "erp_client_secret", "") or "")
        if client_id:
            payload["erpClientId"] = client_id
        if client_secret.strip():
            payload["erpClientSecret"] = client_secret
        return payload

    @staticmethod
    def _safe_config(command: RunCommand) -> Mapping[str, Any]:
        browser = command.lease.config.browser_session
        config = command.lease.config
        safe: dict[str, Any] = {
            "browserSession": {
                "mode": browser.mode,
                "headless": browser.headless,
                "channel": browser.channel,
                "closePolicy": browser.close_policy,
            },
            "dryRun": bool(getattr(config, "dry_run", False)),
        }
        mapped = (
            ("customer_name", "customerName"),
            ("customer_code", "customerCode"),
            ("business_entity", "businessEntity"),
            ("ou", "ou"),
            ("sdms_base_url", "sdmsBaseUrl"),
            ("erp_base_url", "erpBaseUrl"),
            ("oa_base_url", "oaBaseUrl"),
            ("doc_base_url", "docBaseUrl"),
            ("erp_client_id", "erpClientId"),
        )
        for attr, key in mapped:
            value = str(getattr(config, attr, "") or "").strip()
            if value:
                safe[key] = value
        searches = getattr(config, "searches", None)
        if isinstance(searches, list):
            safe["searches"] = [dict(item) for item in searches if isinstance(item, dict)]
        return safe

    @staticmethod
    def _validate_input(
        manifest: FlowManifest,
        input_data: Mapping[str, Any],
    ) -> None:
        expected_types: dict[str, type[Any] | tuple[type[Any], ...]] = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        errors: list[str] = []
        for field in manifest.input_schema:
            if field.name not in input_data:
                if field.required:
                    errors.append(f"{field.name}:required")
                continue
            value = input_data[field.name]
            expected = expected_types[field.type]
            valid = isinstance(value, expected)
            if field.type in {"integer", "number"} and isinstance(value, bool):
                valid = False
            if not valid:
                errors.append(f"{field.name}:type")
        if errors:
            raise RpaBusinessError(
                "FLOW_INPUT_INVALID",
                "Flow input does not satisfy the manifest schema",
                details={"fields": errors},
            )

    async def _verify_work_directory(self, path: Path) -> None:
        try:
            await asyncio.to_thread(self._probe_work_directory, path)
        except PermissionError as exc:
            raise RpaFatalError(
                "RUNTIME_WORKDIR_ACCESS_DENIED",
                "Runtime work directory access was denied",
            ) from exc
        except OSError as exc:
            raise RpaFatalError(
                "RUNTIME_WORKDIR_WRITE_FAILED",
                "Runtime work directory could not be prepared",
            ) from exc

    @staticmethod
    def _probe_work_directory(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".runtime-workdir-{uuid4().hex}.tmp"
        payload = b"nodeskclaw-rpa-engine"
        try:
            probe.write_bytes(payload)
            if probe.read_bytes() != payload:
                raise OSError("Runtime work directory probe read mismatch")
        finally:
            probe.unlink(missing_ok=True)

    def _run_directory(self, run_id: str, lease_id: str) -> Path:
        path = (
            self._work_root
            / self._safe_segment(run_id)
            / self._safe_segment(lease_id)
        ).resolve()
        try:
            path.relative_to(self._work_root)
        except ValueError as exc:
            raise ValueError("Run directory is outside the configured root") from exc
        return path

    def _cleanup(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self._work_root)
        except ValueError:
            return
        shutil.rmtree(path, ignore_errors=True)
        with contextlib.suppress(OSError):
            path.parent.rmdir()

    @staticmethod
    def _safe_segment(value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
        return safe[:100] or "run"
