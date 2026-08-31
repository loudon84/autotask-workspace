# Integration

Contracts between Client, Task, Engine, Auth, and external ERP/SDMS systems.
String IDs cross service boundaries; Engine never FKs into Task tables.

## Client ↔ Auth

Client Main logs in against the NoDeskClaw Auth backend and stores tokens locally.

Typical defaults: auth host `:4510`, prefix `/api/v1/auth`. After login, Client
syncs Task session via `POST /session/sync` so Task can cache `/auth/me` identity
and managed-user scope.

## Client ↔ Task

All Task HTTP uses JWT under `/api/v1/autotask` from Electron Main.

URL builder: [[app/src/types/endpoint-config.ts#buildTaskUrl]]. Covers portals,
bindings, tasks, process/statement SOP, human actions, artifacts, schedulers.
Worker-api may also run on the same machine when the Client hosts a local agent.

## Client ↔ Engine

Client can list/upload/validate/publish Flow packages against Engine `/api/v1`
using actor/tenant headers — not the Task Bearer.

URL builder: [[app/src/types/endpoint-config.ts#buildRpaEngineUrl]]. Day-to-day
runs still go Task → worker lease → Engine; Binding stores the Flow pin Task
already validated.

## Task ↔ Engine

Task validates Binding Flow pins and Engine workers pull leases / push callbacks.

- Validate: Task `rpa_engine_client` → Engine `POST /api/v1/flow-versions/validate-binding`
  (can be disabled with `RPA_ENGINE_VALIDATE_BINDING=false` for constrained labs)
- Lease payload snapshots exact flow id/version/checksum plus portal credentials
  and env integration bases
- Callbacks: Engine Callback Outbox delivers ordered, idempotent EVENT/FINISH to
  Task worker-api finish/event routes

## External Systems

Workers call SDMS/ERP/OA using bases and secrets injected at lease time from Task
`.env`.

Client may open SDMS pages using `GET /integration-endpoints` (`sdmsBaseUrl`).
Outbound HTTP evidence is recorded as [[domain#IntegrationCallLog]]. Redis-backed
command queues remain an open production hardening item when the port is
unreachable.
