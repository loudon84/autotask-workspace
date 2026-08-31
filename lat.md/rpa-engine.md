# RPA Engine

`rpa-engine/` (`nodeskclaw-rpa-engine`) owns Flow Registry metadata, versioned
packages, an internal Worker Pool, and the Playwright Runtime.

Default listen `127.0.0.1:4610`. App factory:
[[rpa-engine/src/nodeskclaw_rpa_engine/api/app.py#create_app]] (module entry
[[rpa-engine/src/nodeskclaw_rpa_engine/main.py#app]]). Nested detail graph:
`rpa-engine/lat.md/`.

## Responsibilities

Engine executes published Flows; it does not own business tasks or HumanAction.

Owns: Flow Registry (`GLOBAL`/`TENANT`), package validation/publish, worker
instances, `rpa_execution_attempts`, callback outbox, MANAGED browser sessions,
artifact upload helpers, structured errors/logging. Does **not** own
AutomationTask, WorkflowBinding, RpaRun business rows, or portal credentials
tables — those stay on Task (see [[design-decisions#Ownership Split]]).

## Module Map

Source under `src/nodeskclaw_rpa_engine/` mirrors phase boundaries.

- `api/` — FastAPI assembly, health, flows, workers
- `core/` — settings, readiness, logging/redaction
- `db/` — async SQLAlchemy + Engine schema models (`rpa_engine`)
- `flows/` — registry, manifest, package validation
- `workers/` — pool, lease source, resolver, Task client, outbox
- `runtime/` — loader, browser, context, artifacts, credentials, errors
- `mock_srm/` — deterministic local supplier portal for demos

## Execution Sketch

Lease → exact version resolve → attempt RUNNING → `flow.py:run(ctx)` → FINISH
outbox.

Runtime validates optional JSON SUCCESS output (encoding, forbidden sensitive
keys, size). Feature flags gate DB, object storage, Worker, and Runtime so a
disabled-dependency profile can boot without Postgres/MinIO.

## Operator Notes

Upload/publish/verify flows via Engine HTTP APIs; workers poll Task worker-api
when lease polling is enabled.

Package Python 3.12. Prefer exact published versions in Binding before live
lease smoke tests. On Ubuntu, prefer workspace [[architecture#Local Ubuntu Bring-Up|`dev.sh`]]
so Chromium lands under `PLAYWRIGHT_BROWSERS_PATH` before Engine starts. Deeper
section map: architecture, flow-registry, worker-pool, runtime, callback-outbox,
configuration, health-logging, data-model, integration-boundaries inside
`rpa-engine/lat.md/`.
