# Data Model

The Engine owns nine tables in the PostgreSQL `rpa_engine` schema. The application
never creates or migrates them.

The ORM models in `src/nodeskclaw_rpa_engine/db/models/` mirror the operator-controlled
SQL baseline in `sql/0002_rpa_engine_initial_schema.sql`. Each connection sets its own
`search_path` to `rpa_engine,public` via
[[src/nodeskclaw_rpa_engine/db/session.py#DatabaseManager]]. Cross-schema references to
`nodeskclaw_task` are by ID only — there are no cross-schema foreign keys.

## Engine-Owned Tables

The nine tables split across three model modules:

- `db/models/flow.py` — `rpa_flows`, `rpa_flow_versions`, `rpa_flow_validation_runs`,
  `rpa_flow_release_audits` (see [[data-model#Flow Tables]]).
- `db/models/execution.py` — `rpa_worker_instances`, `rpa_execution_attempts`,
  `rpa_callback_outbox` (see [[data-model#Execution Tables]]).
- `db/models/browser.py` — `rpa_browser_profiles`, `rpa_cdp_endpoints` (see
  [[data-model#Browser Tables]]).

## Flow Tables

`rpa_flows` holds the stable `flow_key` identity with `GLOBAL`/`TENANT` scope and
`ACTIVE`/`DISABLED`/`ARCHIVED` status.

`rpa_flow_versions` holds the immutable manifest, package metadata (bucket, object
key, size, SHA-256), and the `DRAFT`/`VALIDATING`/`PUBLISHED`/`DEPRECATED`/`DISABLED`
status constrained by triggers — a `PUBLISHED` row must have complete package metadata
and `published_at`. `rpa_flow_validation_runs` records upload/manual/publish/CI
validation results. `rpa_flow_release_audits` is an append-only audit trail of
publication actions.

## Execution Tables

`rpa_worker_instances` is the Engine-internal Worker state (public `rpa_workers`
remains Task's dispatch authority).

`rpa_execution_attempts` is the technical attempt with `LEASE`/`QUEUE` dispatch mode, a
per-run `attempt_no`, input and browser-session snapshots, and the
`LEASED`/`RUNNING`/`SUCCESS`/`FAILED`/`WAITING_HUMAN`/`CANCELLED`/`ABANDONED` status.
`lease_id` and `command_id` are unique where non-null. See
[[worker-pool#Attempt Lifecycle]]. `rpa_callback_outbox` stores ordered, idempotent
EVENT/FINISH/ARTIFACT callbacks to Task. See [[callback-outbox]].

## Browser Tables

`rpa_browser_profiles` and `rpa_cdp_endpoints` are reserved for future
`PERSISTENT_PROFILE` and `CDP_ATTACH` browser sessions.

Both default to `DISABLED` and are not used by the current MANAGED-only Runtime. See
[[runtime#Managed Browser Session]].
