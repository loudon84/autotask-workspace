# Postman

Import `AutoTask_RPA_Engine_v0.5.0.postman_collection.json`. The collection
targets `http://localhost:4610` by default; override `engine_base_url` when
testing another environment. Requests use noauth; `X-Actor-Id` / `X-Tenant-Id`
headers are injected by a collection-level prerequest script for audit context
only.

The collection covers all 17 Engine routes, grouped as: Health -> Flow
Discovery -> Registry Write -> Binding Contract -> Worker Observability ->
Package -> Lifecycle (manual only). It contains only Engine inbound APIs;
the Engine polls the Task Worker API outbound, so there is no inbound `/run`.

Mutating requests are guarded and skipped by default:

- Registry Write requests require `allow_registry_writes=true`.
- Lifecycle requests require `allow_lifecycle_changes=true` and are meant to
  be run one at a time by hand.

Before `Upload Flow Package`:

1. Build the ZIP from `examples/phase2-demo`.
2. Select the ZIP in Postman's `package` file field. Some Postman versions do
   not resolve a collection variable as a local file path.
3. Increment the manifest version before repeating an upload; versions cannot
   be overwritten.

The upload request stores `flow_id`, `flow_version`, and `flow_version_id`
into collection variables for subsequent requests.

The collection is kept in sync with the code by
`tests/test_postman_engine_collection.py`, which fails if routes, variables,
or safety guards drift.

Historical `RPA_Engine_Phase2` / `RPA_Engine_Phase3` collections were removed;
the v0.5.0 collection is a superset of both. Phase 4 and Phase 5 added no
Engine HTTP endpoints, so they have no collection: Runtime is invoked through
the internal Worker `RunCommandHandler` (`docs/PHASE4_RUNTIME.md`), and the
Mock SRM harness is documented in `docs/PHASE5_MOCK_SRM.md`.
