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

## Formal Drill Shares Production Flow

Official portal drill and real go-live share the same Flow package; demo vs
official portals may still use different packages.

Drill knobs (`treatAsPending`, `dryRun`, sample PO) belong in Binding config, not
forked Flow trees. See product SOP under `project-docs/prd/`.

## Database Hold Point

DDL and designs may be prepared; executing create/migrate/seed requires explicit
user authorization except where already recorded as authorized in project control.

Engine and Task share the conceptual product DB historically named
`nodeskclaw_task` with Engine schema `rpa_engine` in current test baselines;
production isolation targets remain documented in project control.
