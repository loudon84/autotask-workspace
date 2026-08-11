# Architecture

NoDeskClaw RPA Engine owns Flow Registry metadata and Flow Packages, and executes
published Flows inside MANAGED Playwright sessions.

The Engine is a FastAPI service (default `127.0.0.1:4610`) on Python 3.12. It does not
own business tasks, runs, Workflowbinding, or HumanAction — those belong to
`nodeskclaw-task`. The Engine owns only the technical execution attempt and the
callbacks it sends back to Task. See [[integration-boundaries#Ownership Boundary]].

## Module Map

The source layout mirrors the phase boundaries described in `docs/INDEX.md`.

- `api/` — FastAPI assembly, lifespan, exception mapping, and route modules for
  `health`, `flows`, and `workers`. Entry point is [[architecture#App Assembly]].
- `core/` — cross-cutting infrastructure: [[configuration#Settings]], readiness, and
  [[health-logging#Structured Logging and Redaction]].
- `db/` — async SQLAlchemy session manager and the Engine-owned ORM models in
  [[data-model#Engine-Owned Tables]].
- `flows/` — Flow Registry domain: manifest, package validation, repository, and
  service. Described in [[flow-registry]].
- `workers/` — internal Worker Pool, lease source, resolver, Task client, and the
  callback outbox. Described in [[worker-pool]] and [[callback-outbox]].
- `runtime/` — the RPA execution engine: loader, browser, context, artifacts,
  credentials, errors, and callbacks. Described in [[runtime]].
- `mock_srm/` — a deterministic local supplier-portal used by Phase 5 demos.
- `main.py` / `__main__.py` — process entry points.

## App Assembly

`create_app` wires every component from [[configuration#Settings]] and constructs only
what the enabled feature flags require.

A disabled-dependency profile starts without a database, object storage, Task client,
Worker Pool, or Runtime. Tests inject probes and services instead of real external
clients. The lifespan starts the [[callback-outbox#Dispatcher]] before the
[[worker-pool]] and stops them in reverse order, always closing the Task client,
database, and object storage even when a component fails.

## Execution Flow

A leased run flows through these layers:

1. [[worker-pool#Lease Source]] receives a `LeaseRunCommand` from Task.
2. [[worker-pool#Flow Version Resolver]] resolves the exact published Registry
   version — the Engine never falls back to the latest version.
3. The Worker Pool records an `rpa_execution_attempts` row and transitions it to
   `RUNNING`.
4. [[runtime#RpaRuntime]] loads the package, opens a MANAGED browser, builds a
   `RunContext`, and runs `flow.py:run(ctx)` with retry and lease renewal.
5. The Runtime returns a terminal `RunResult` (`SUCCESS`, `FAILED`, or
   `WAITING_HUMAN`).
6. The Worker Pool persists the terminal attempt and enqueues a FINISH callback via
   [[callback-outbox#CallbackOutboxService]].

## Dependency Gating

Feature flags are gated by [[configuration#Dependency Gating]].

Worker requires the database and required capabilities; Runtime requires object
storage; lease polling requires a Runtime `RunCommandHandler`. Nothing auto-creates
schema, tables, or buckets. See [[configuration#External Dependency Policy]].
