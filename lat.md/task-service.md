# Task Service

`service/` (`nodeskclaw-task`) is the FastAPI business API that orchestrates
AutoTask work without executing browser RPA itself.

Default listen `:4520`, prefix `/api/v1/autotask`. Entry app:
[[service/app/main.py#app]].

## Layering

HTTP routers sit on services, SQLAlchemy models, and Pydantic camelCase schemas.

- `app/api/` — Client JWT API, worker-api, and MCP tools
- `app/services/` — domain logic (dispatch, tasks, process, statement, jobs)
- `app/models/` / `app/schemas/` — persistence and wire contracts
- `app/core/` — settings, deps, security, middleware
- `alembic/` — migrations (auto `upgrade head` unless `SKIP_AUTO_MIGRATE`)

## HTTP Surfaces

Three mounts share the same process.

1. **Client API** (`/api/v1/autotask/*`) — JWT user calls for dashboard, portals,
   templates, bindings, tasks, process-instances, statements, runs, human-actions,
   artifacts, timers.
2. **Worker API** (`/api/v1/autotask/worker-api/*`) — register/heartbeat, lease,
   renew, run events/artifacts/integration-calls/finish, mail OTP watermark/fetch.
3. **MCP** (`/api/v1/autotask/mcp`) — thin tools over the same services.

Envelope type is `ApiResponse`. Root `GET /health` exposes pid/version.

## Orchestration

Task is the queue owner: lease → run callbacks → state machine → successors.

Lease/finish logic lives in [[service/app/services/dispatch_service.py#lease_task]].
State transitions use
[[service/app/services/task_state_machine.py#TRANSITIONS]]. Process and statement
services advance multi-stage SOP when sub-tasks finish. Successor jobs enqueue
follow-on bindings after SUCCESS.

## Schedulers


Background work is one [[service/app/services/timer_scheduler.py#TimerScheduler]]
sync loop feeding APScheduler CronTrigger jobs; due time comes from the library,
not a handmade tick.

Binding `JobScheduler` and the old `.env` / `autotask_settings` loops are gone
(`project-docs/prd/AutoTask 调度中心-清场.md`); the library landed per
`project-docs/prd/AutoTask 调度中心-引入APScheduler.md`. Crontab dow `0`/`7`
=Sunday is shimmed by [[service/app/services/unix_cron.py#to_apscheduler_crontab]]
before `from_crontab`.

- Independent timers: [[service/app/models/timer.py#Timer]], `/timers` API,
  [[service/app/services/timer_registry.py#notify]]
- Catalog upsert on boot: [[service/app/services/timer_service.py#ensure_catalog_rows]];
  existing rows keep their enabled/cron. [[service/app/services/timer_catalog.py#REGISTRATIONS]]
  holds demo plus
  [[service/app/services/tiandy_timers.py#scan_pending_due|tiandy scan]] /
  [[service/app/services/tiandy_timers.py#sign_poll_due|sign-poll]] /
  [[service/app/services/boe_timers.py#pack_match_due|boe pack-match]] /
  [[service/app/services/boe_timers.py#srm_login_due|boe srm-login]]
- Scan work stays in [[service/app/services/scan_scheduler.py#run_scan_once]]
- Every due fire lands in `timer_runs`; missing table still notifies
- `POST /timers/{id}/run` bypasses enabled/cron
- Optional successor processor remains env-gated (`SUCCESSOR_JOB_*`)

## Persistence

PostgreSQL via SQLAlchemy 2 async + asyncpg; soft delete via `deleted_at`.

Artifacts may be local disk or S3. Integration call logs support ops diagnosis.
Task does not store Engine Registry rows; it stores Binding pins and run
metadata only.

`portal_accounts.category` stores a hardcoded code (`TIANDI` / `BOE`). Customer-order
and statement lists join portals and keep `TIANDI` only; scan jobs reject other
codes. Category handbooks use the same code on `category_documents` and live on
Task disk. See [[design-decisions#Portal Category Is Hardcoded]].
