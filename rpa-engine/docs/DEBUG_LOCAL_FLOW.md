# Local Flow Debugging

Debug any Flow package end-to-end through the real `RpaRuntime` without the Worker Pool, Callback Outbox, or Task API.

## Script

`scripts/debug_flow_local.py` mirrors the production wiring in `api/app.py` (`FlowLoader` + `ManagedBrowserSessionManager` + `RpaRuntime`) but swaps three Task-API-backed dependencies for local equivalents:

- **Package source** — serves the Flow ZIP from a local directory or `.zip` file instead of object storage.
- **Artifact sink** — writes screenshots/downloads to a local directory instead of Task signed-URL upload.
- **Event sink** — prints every `STEP_*` / `RUNTIME_*` event to the console instead of the Callback Outbox.
- **Credential resolver** — simple username/password resolver from CLI args (no governed credential service).

## One-click launcher

`scripts/debug_manifest_flow.ps1` is the one-click entry point. It resolves the
repository root, picks the project venv interpreter, defaults the package to
`manifest/rpa_flow_supplier_portal_prepare_erp_order/1.2.3`, and forwards every
extra argument to `scripts/debug_flow_local.py`.

```powershell
.\scripts\debug_manifest_flow.ps1 -PoNo PO12345
.\scripts\debug_manifest_flow.ps1 -Package manifest/rpa_flow_login_demo/1.1.0 -PoNo PO123 -Headless
```

Only `-PoNo` is required; `-Package`, `-PortalUrl`, `-Username`, `-Password`,
`-Channel`, `-Headless`, `-NoCleanup`, and `-Artifacts` are optional and any
remaining arguments pass straight through to the underlying Python harness.

## Usage

From the repo root with the project venv active:

```powershell
.\.venv\Scripts\python.exe scripts\debug_flow_local.py `
  --package manifest/rpa_flow_supplier_portal_prepare_erp_order/1.2.3 `
  --po-no PO12345
```

Common options:

- `--portal-url` — supplier portal base URL (default `http://127.0.0.1:4700`, the mock SRM).
- `--username` / `--password` — portal credentials.
- `--headless` — run without a visible browser window.
- `--channel` — `chromium` (default), `chrome`, or `msedge`.
- `--artifacts` — local artifact output directory (default `runtime-cache/debug-artifacts`).
- `--no-cleanup` — keep the runtime work directory for post-run inspection.

## Execution order (inferred from the package + engine)

For Flow package `1.2.3` the runtime pipeline is:

1. `RpaRuntime.handle` binds log context, verifies the run work dir.
2. `FlowLoader` fetches/validates the package (ZIP structure, manifest identity, `minimumEngineVersion`, SHA-256), extracts to `runtime-cache/flows/...`, and loads `flow.py:run`.
3. Input is validated against `manifest.json#inputSchema` (`po_no` required string).
4. Credentials resolved via the configured resolver.
5. `ManagedBrowserSessionManager` launches Playwright (`MANAGED` mode) and returns a single `Page`.
6. `RunContext.create` assembles the frozen capability surface: `input`, `credentials`, `page`, `portal_url`, `selectors`, `artifacts`, `log`, `events`, `config`.
7. `RpaRuntime._execute_with_retries` calls `run(ctx)` with timeout/retries.
8. Inside `flow.py`:
   - `_prepare_erp_order` → portal login → open PO detail → collect line identities → download XLSX → `parse_order_xlsx` → `reconcile_attachment_with_portal` → `build_erp_draft` → stability wait + screenshot.
   - `ErpSalesOrderClient.fetch_access_token` → `import_sales_order` → map result rows to `orderNumber`.
   - Return structured output (`schemaVersion`, `poNo`, `orderNumber`, `supplierCode`, `supplierName`, `lineCount`, `lines`).
9. `RpaRuntime` validates output (JSON object, no sensitive keys, size cap) and emits `RUNTIME_SUCCEEDED`.
10. On failure it captures a screenshot + optional trace, classifies the error (`FAILED` / `WAITING_HUMAN`), and emits `RUNTIME_FAILED` / `RUNTIME_WAITING_HUMAN`.

## Debugging

Set breakpoints in `manifest/.../1.2.3/flow.py` (e.g. `run()`, `_prepare_erp_order`, `parse_order_xlsx`) or in engine modules under `src/nodeskclaw_rpa_engine/runtime/` and launch `scripts/debug_flow_local.py` under your debugger. All flow events and the final `RunResult` are printed to the console; artifacts land under `--artifacts`.
