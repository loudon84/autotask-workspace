# Flow Registry

The Flow Registry owns versioned RPA Flow packages and their metadata, validates
uploaded ZIP packages, and enforces a trigger-constrained publication state machine.

The Registry is exposed by the Phase 2 API in `docs/PHASE2_API.md` and implemented by
[[src/nodeskclaw_rpa_engine/flows/service.py#FlowRegistryService]]. It persists to the
`rpa_flows`, `rpa_flow_versions`, `rpa_flow_validation_runs`, and
`rpa_flow_release_audits` tables in [[data-model#Flow Tables]].

## Flow Identity

A Flow is a stable identity (`rpaFlowId` / `flow_key`) that carries one or more immutable
versions. Scope is `GLOBAL` or `TENANT`; a `TENANT` Flow requires `X-Tenant-Id` and is
namespaced by a SHA-256 of the tenant id in the object key.

The same Flow + version can never be overwritten; re-uploading an existing version is
rejected with `FLOW_VERSION_EXISTS`. Object keys are immutable and never store signed
URLs. See [[flow-registry#Scope and Tenant Namespacing]].

## Manifest

`manifest.json` is the package contract, modeled by
[[src/nodeskclaw_rpa_engine/flows/manifest.py#FlowManifest]].

It pins `engineType=PLAYWRIGHT_CDP`, `entrypoint=flow.py:run`, a semver `version`, at
least one `supportedWorkflowCodes`, an optional `inputSchema`, and an optional
`minimumEngineVersion`. The manifest uses `extra="forbid"` so unknown fields are
rejected.

## Package Validation

[[src/nodeskclaw_rpa_engine/flows/package.py#FlowPackageValidator]] validates a ZIP
without importing or executing `flow.py`.

It enforces size, file-count, and compression-ratio limits from
[[configuration#Settings]], requires root `manifest.json` and `flow.py`, rejects unsafe
paths, symlinks, encrypted entries, and sensitive file names (`.env`,
`credentials.json`, `secrets.json`), and AST-checks the entrypoint.

### Entrypoint AST Check

`flow.py` must define a top-level `async def run(ctx)` with `ctx` as the first
parameter. The validator parses the AST only — it never imports the module.

### Runtime Policy Check

Every `.py` file in the package is AST-scanned for forbidden imports and calls.

Forbidden imports are `asyncpg`, `playwright`, `psycopg`, `sqlalchemy`; forbidden calls
include `async_playwright`, `launch`, `connect_over_cdp`, and `open`. This is a static
policy check, not OS-level isolation. See [[runtime#Flow Sandboxing]].

## Version State Machine

Publication is constrained by database triggers and the service.

```text
DRAFT -> VALIDATING -> PUBLISHED -> DEPRECATED
                         |              |
                         +-> DISABLED <-+
```

`publish_version` re-validates the package from object storage, checks the SHA-256
against stored metadata, and only then transitions to `PUBLISHED`. A version that is
already `PUBLISHED` is idempotent. `DEPRECATED` and `DISABLED` are reached through
`deprecate_version` and `disable_version`.

## Rollback

`rollback_flow` re-publishes a previously `PUBLISHED` or `DEPRECATED` version and
deprecates every other currently-published version of the same Flow.

Registry rollback only changes version status; it never rewrites `Workflowbinding`
records in `nodeskclaw-task`. Binding rollback is the Task service's responsibility.

## Scope and Tenant Namespacing

`_package_object_key` builds the object key as
`flows/{namespace}/{rpaFlowId}/{version}/{uploadId}-{checksum}.zip`.

Namespace is `global` or `tenant/{sha256(tenantId)}`. A failed upload transaction
deletes the uncommitted object and rolls back the database row.

## Binding Validation

`validate_binding` is the Task-facing contract check.

Given a version id (or `rpaFlowId` + `version`) and optional `workflowCode`, it returns
whether the version is `ACTIVE` + `PUBLISHED` and supports the workflow code. The
response carries temporary deprecated aliases for Task compatibility; the
authoritative snapshot is nested under `version`.

## Error Mapping

Registry errors are [[src/nodeskclaw_rpa_engine/flows/errors.py#FlowRegistryError]]
with a stable `code`, `message`, HTTP `status_code`, and optional `details`.

`PackageValidationError` is the 422 subtype carrying a list of issue objects. The
FastAPI exception handler in [[architecture#App Assembly]] renders them as
`{"error": {...}}`. Request-validation failures use `REQUEST_VALIDATION_FAILED` and
never echo raw input.
