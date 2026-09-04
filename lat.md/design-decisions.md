# Design Decisions

Cross-cutting decisions that keep Client, Task, Engine, and Flow packages
aligned. Prefer these over reinventing boundaries in any one root.

## Ownership Split

Task owns business orchestration; Engine owns Flow Registry and technical
execution.

Task: portals, templates, bindings, AutomationTask, RpaRun metadata, HumanAction,
process/statement SOP, schedulers. Engine: flow versions, worker instances,
execution attempts, callback outbox, browser profiles (future). No FK from Engine
tables into Task tables — only external string IDs.

## Exact Flow Version Pinning

Bindings and leases pin an exact published Flow version and checksum; Engine
never falls back to “latest”.

This prevents silent drift when a newer package is published. Validation goes
through Engine `validate-binding` before Task accepts the pin.

## Env-Level Integration Bases

SDMS/ERP base URLs and secrets live in Task process `.env` (lease config), not
in Binding JSON or Flow source.

Changing test vs production hosts is an ops restart/config change. Binding keeps
business parameters (`searches`, `dryRun`, sample PO). Portal passwords belong on
PortalAccount, not in Client login settings or Flow code.

## Flow Sandbox Contract

Flows only automate through `RunContext`; they do not own browser lifecycle or
business DB access.

Entry is `flow.py:run(ctx)`. Playwright + CDP is managed by Engine (`MANAGED`
first; `PERSISTENT_PROFILE` / `CDP_ATTACH` are controlled extensions). Artifacts
and errors go through Runtime helpers.

## Human-In-The-Loop Is First Class

`WAITING_HUMAN` plus HumanAction is a supported terminal/resume path, not an
afterthought.

OCR and fragile portal steps must keep a human fallback. WAITING_HUMAN does not
resume the original server browser session (type-A model).

## Client Remote-By-Default With Main-Side HTTP

The Electron Client defaults to remote API mode; all Task/Auth/Engine HTTP runs
in Main, not Renderer.

Mode switch: [[app/src/types/endpoint-config.ts#getApiMode]] (default `"remote"`).
Renderer uses oRPC actions and the `autotaskApi` facade. Tokens stay in Main
encrypted/file stores. Mock mode remains switchable for offline UI work.

## Soft Delete and Federated Auth

Task uses soft delete and tenant_id throughout; auth is federated JWT from the
NoDeskClaw backend with a TTL user cache.

No local password store in Task. Portal ACL uses ownership and managed-user
scope rather than treating grants as the primary filter.


## BOE SOP Reuses Process Instances

BOE packing reuses `process_instances`. v2.1 splits scan, WMS, enrich, save-draft,
and submit so each failed node retries alone; v2.2 keeps `BOE_PACK_*` codes but
renames displays from the CS point of view.

Unlike 天地伟业, matching is tenant-level HTTP (delivery plan already has
subcode and factory), not a per-portal SRM scan. Cookie is shared per SRM
username. Qty mismatch is shown through save-draft but only hard-blocks CS
submit. Client header shows key fields only (portal customer fields read-only;
volume unit fixed 立方米). Phase 1 skips attachments and AutoTask OTP. See
[[domain#BoeInvoicePacking]].

Phase 1 is implemented: `/boe-packing` + tenant match timer on 调度中心
(default off, hot-reload cron), three templates/Flows, Client list/detail with
review diff, region-map API. WMS lines use `cuspo`/`cusitem`/`qty`/`netweight`/`cubic`/`coo`; header
volume is sum(`cubic`). Do not run Alembic `b2d4f6a81935` until authorized;
tonight's official v5.5 migrate must stop at `a1c3e5f70824`, not `head`.

## Portal Category Is Hardcoded

Portal category codes (`TIANDI`, `BOE`) are hardcoded. Users only pick a
category on each portal; process menus and SOPs bind to that code.

Do not add a user-maintained parent-portal or process-catalog table: SOP UI and
Flows are written per customer. Live 天地伟业 portals backfill to `TIANDI`
without changing instance keys or routes. Category handbooks also bind to that
code (`category_documents.category`) and files live on the Task server disk.
See `project-docs/prd/tiandy/AutoTask v5.5 门户和流程实例优化.md`.


## Formal Drill Shares Production Flow

Official portal drill and real go-live share the same Flow package; demo vs
official portals may still use different packages.

Drill knobs (`treatAsPending`, `dryRun`, sample PO) belong in Binding config, not
forked Flow trees. See product SOP under `project-docs/prd/`.

## Independent Timers

Independent timers are archives with name, enabled, cron, and an opaque target;
due ticks only notify a registry.

The 调度中心 UI never shows target, portal, or Binding. Empty
[[service/app/services/timer_catalog.py#REGISTRATIONS]] is valid until a task
registers. Binding JobScheduler may run in parallel until old jobs are moved.
See [[domain#SchedulerJob]].

## Database Hold Point

DDL and designs may be prepared; executing create/migrate/seed requires explicit
user authorization except where already recorded as authorized in project control.

Engine and Task share the conceptual product DB historically named
`nodeskclaw_task` with Engine schema `rpa_engine` in current test baselines;
production isolation targets remain documented in project control.
