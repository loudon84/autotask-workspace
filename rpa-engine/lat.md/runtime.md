# Runtime

The Runtime executes a single resolved Flow inside a MANAGED Playwright session and
returns a terminal `RunResult`. It is the Phase 4 `RunCommandHandler` injected into
the [[worker-pool]].

The Runtime is implemented by [[src/nodeskclaw_rpa_engine/runtime/engine.py#RpaRuntime]]
and documented in `docs/PHASE4_RUNTIME.md`. It owns Flow loading, browser lifecycle, the
run context, artifacts, error mapping, and structured output validation.

## RpaRuntime

`RpaRuntime.handle` is the single entry point for one run.

It binds log context, verifies the run work directory, loads the Flow, validates input,
resolves credentials, starts the browser, builds a `RunContext`, executes with
retries, captures failure screenshots and trace, and emits run events. The Worker Pool
owns attempt status and the FINISH callback; the Runtime only returns `SUCCESS`,
`FAILED`, or `WAITING_HUMAN`.

## Flow Loader

[[src/nodeskclaw_rpa_engine/runtime/loader.py#FlowLoader]] downloads the exact package
from object storage and verifies SHA-256 against the Registry snapshot.

It re-runs package validation, checks manifest identity and `minimumEngineVersion`,
and atomically extracts into
`RUNTIME_CACHE_DIR/{rpaFlowId}/{version}/{checksum}`. A `.ready` marker file stores the
checksum so the cache is reused only when it matches.

## Managed Browser Session

[[src/nodeskclaw_rpa_engine/runtime/browser.py#ManagedBrowserSessionManager]] starts
Playwright and returns a single `Page` from a managed `BrowserContext`.

Only `mode=MANAGED` is supported; `profileRef` and `cdpEndpointRef` must be null;
`closePolicy` must be `ALWAYS` or `CLOSE_ON_FINISH`. Channels are `chromium`, `chrome`,
and `msedge`.

## Run Context

[[src/nodeskclaw_rpa_engine/runtime/context.py#RunContext]] is the frozen capability
surface handed to `flow.py:run(ctx)`.

It exposes immutable `input`, `credentials`, `selectors`, and a safe `config` (browser
session without Profile/CDP references), plus the managed `page`, an `artifacts`
recorder, and `log`/`events` sinks. Flow code never receives references that could open
its own browser or reach the database.

## Flow Sandboxing

Flow Python modules execute in the Engine process.

Package validation rejects imports of `playwright`, `sqlalchemy`, `asyncpg`,
`psycopg` and direct browser/CDP/`open()` calls (see
[[flow-registry#Package Validation#Runtime Policy Check]]). This is a static policy
check, not OS-level isolation; process or container isolation is a future hardening
decision.

## Artifacts

[[src/nodeskclaw_rpa_engine/runtime/artifacts.py#ArtifactRecorder]] writes
screenshots, downloads, trace, and logs under the run directory.

It checks paths stay inside the run root, enforces `ARTIFACT_MAX_BYTES`, and computes
SHA-256. The [[src/nodeskclaw_rpa_engine/runtime/artifacts.py#TaskArtifactSink]]
delivers each file through Task `POST /worker-api/artifacts/upload-url`, a signed PUT,
and a run artifact metadata callback. Signed URLs are never persisted and are redacted
in logs.

## Credentials

[[src/nodeskclaw_rpa_engine/runtime/credentials.py#build_credential_resolver]] builds
the configured resolver.

The default `DisabledCredentialResolver` rejects any non-null `credentialRef`. The
`mock_env` resolver is restricted to `development`/`test`, a single credential
reference, tenant, and Portal account, and is only for controlled Phase 5 demos.
Production requires a governed credential-service adapter.

## Error Mapping

[[src/nodeskclaw_rpa_engine/runtime/errors.py#ErrorHandler]] classifies exceptions
into an `ErrorDecision`.

`RpaRetryableError`, Playwright/Python timeouts retry up to `RUNTIME_MAX_RETRIES` then
`FAILED`. `RpaBusinessError` and `RpaFatalError` are `FAILED`.
`RpaHumanRequiredError` is `WAITING_HUMAN`. Unknown exceptions become `FAILED` with the
safe code `FLOW_UNHANDLED_ERROR`. Filesystem errors use `FLOW_CACHE_*` and
`RUNTIME_WORKDIR_*` codes and never leak absolute paths.

## Structured Output

A successful `flow.py:run(ctx)` may return a JSON object.

`_validate_output` requires a `dict`, strict JSON (no `NaN`/`Infinity`, string keys),
rejects sensitive field names, and enforces `RUNTIME_OUTPUT_MAX_BYTES`. Violations are
fatal (`FLOW_OUTPUT_INVALID` / `FLOW_OUTPUT_TOO_LARGE`) and are not retried, because the
Flow may already have produced external side effects. Output is only carried on
`SUCCESS` and is never written to Engine logs.

## Trace Modes

`RUNTIME_TRACE_MODE` is `OFF`, `ON_FAILURE`, or `ALWAYS`.

Trace is uploaded as `trace.zip` through the artifact sink. When cleanup runs, an
unrecorded trace is discarded. With `RUNTIME_CLEANUP_ON_FINISH=true` the run directory
is removed after browser cleanup.

## Local Debug Harness

`scripts/debug_flow_local.py` runs a Flow package through the real `RpaRuntime` without
the Worker Pool, Callback Outbox, or Task API.

It mirrors the production wiring in `api/app.py` (`FlowLoader` +
`ManagedBrowserSessionManager` + `RpaRuntime`) but injects a local package source, a
console event sink, and a local-file artifact sink. Use it to execute and debug a Flow
end-to-end with breakpoints from the repo root.

`scripts/debug_manifest_flow.ps1` is the one-click PowerShell entry point for the
harness. It resolves the repo root, selects the project venv interpreter, defaults the
package to `manifest/rpa_flow_supplier_portal_prepare_erp_order/1.2.3`, and forwards all
extra arguments to `debug_flow_local.py`. Only `-PoNo` is required.
