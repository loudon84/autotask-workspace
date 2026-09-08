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
volume unit fixed 立方米). Phase 1 skipped AutoTask OTP; that is superseded by
[[domain#MailInbox]] (Task IMAP + `boe.srm_login`, design 2026-09-08). See
[[domain#BoeInvoicePacking]].

Phase 1 is implemented: `/boe-packing` + tenant match timer on 调度中心
(default off, hot-reload cron), three templates/Flows, Client list/detail with
review diff, region-map API. The three Flows (`rpa_flow_srm_boe_pack_*` 1.0.3)
are published to the Registry and bound (ENABLED) on the demo portal
C000142-01 via `service/scripts/boe/bind_boe_pack_flows.py` (2026-09-07;
1.0.1 realigns login/navigation with the 影刀 recording after a login-step
timeout on 1.0.0; 1.0.2 fixes create-page gating found by live-DOM probes:
启用AI识别 defaults to 是 and locks the whole form, and 项目信息「新增」
requires BOE 工厂 chosen via the 「获取工厂」 dialog first; 1.0.3 fixes the
bsrm sidebar race — the menu mounts late and its init re-render collapses a
just-opened 送货管理 submenu, so navigation retries until 发票箱单 stays
visible — and parses the backfilled 项目信息 row from BOTH the fixed-column
clone (序号~物料编码) and the main table (物料描述起), since el-table splits
them into separate tbodies; 1.0.4/1.0.5 fix 总体积 filling — the
el-input-number carries a static `aria-disabled="true"` so Playwright `fill()`
refuses it (30s timeout), but the input is NOT actually disabled: force-click
+ `keyboard.type` fills it and Vue accepts the value (live-probe verified,
matching the user's manual experience). save_draft/submit now use
`_fill_input_number` (keyboard typing with JS native-setter fallback), and
`prepare_invoice_create` verifies the factory input value after the dialog
confirm, retrying once before raising `BOE_FACTORY_NOT_SET`; 1.0.7 fills
本次开票数/净重/原产国地区 on the backfilled item row (el-select
`placeholder=国/地区` + `regionSrmName`) and deletes the seeded 双签PO/协议
attachment row before 保存, because an empty dual-sign row blocks draft save
and phase 1 still does not upload files). Engine-side: `RunContext` is a frozen dataclass,
so runtime helpers must never assign `ctx.page` — `open_invoice_packing`
returns the active page instead, and `ArtifactRecorder` screenshots the most
recently opened page so failure captures follow tab switches. The WMS endpoint is `/aiats/wms_sjh_pl_boe` with `erpno` and a flat
line array (`cuspo`/`cusitem`/`qty`/`netweight`/`cubic`/`coo`); header volume is
sum(`cubic`) (verified 2026-09-08). `doc_no` now returns `[]`. Alembic `b2d4f6a81935`
(region maps, wide table) migrated on the test DB 2026-09-07 after user
authorization; production DB not migrated yet.

## Region Map Wide Table

Region codes live in one wide row per `(tenant_id, region_code)`: required `default_name` plus nullable per-SRM columns (`boe_name`). An empty SRM column falls back to the default name, so only differing regions need per-SRM maintenance.

Most regions display the same name in every SRM; a long table (one row per
category) would force operators to maintain the same name N times. A new SRM
that needs origin mapping adds its column (e.g. `tiandy_name`) in the Alembic
migration shipped with that SRM's onboarding development — the wide table only
reserves the slot. SRMs without a column always read `default_name`. Rows are
maintained manually on sidebar 管理中心 → 基础数据 → 原产地
(`/base-data/region-maps`); no lazy creation during matching (unmapped codes
surface as red-flagged lines for manual review instead).

## Portal Category Is Hardcoded

Portal category codes (`TIANDI`, `BOE`) are hardcoded. Users only pick a
category on each portal; process menus and SOPs bind to that code.

Do not add a user-maintained parent-portal or process-catalog table: SOP UI and
Flows are written per customer. Live 天地伟业 portals backfill to `TIANDI`
without changing instance keys or routes. Category handbooks also bind to that
code (`category_documents.category`) and files live on the Task server disk.
See `project-docs/prd/tiandy/AutoTask v5.5 门户和流程实例优化.md`.


## Portal Extra Is JSONB

Category-specific portal fields live in JSONB `extra` plus descriptors, not new
table columns. Shared fields stay real columns; BOE CS mailbox is `extra.email`.

Do not add a column per customer (wide-table migrations). Descriptors in
[[service/app/domain/portal_extra.py#EXTRA_FIELDS_BY_CATEGORY]] declare key,
label, type, and required; normalize drops unknown keys. Client loops those
descriptors for form and detail. Adding a field later is a descriptor change,
not Alembic.

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

## Mail Reader Is Scene-Based

Mail reading belongs on Task as IMAP plus scene handlers, not as an OTP-only
script inside Engine or a Flow package.

BOE verification-code mail is scene `boe_srm_otp`. Future order mail uses the
same connector. One system IMAP login; SRM accounts and CS mailboxes come from
BOE portal rows (`login_account` + `extra.email`), not `.env`. A code is used
only if it belongs to this Get-Code click (To + UID watermark + 5-minute TTL).
Auth lives in Task `.env` only. See [[domain#MailInbox]] and
[[design-decisions#OTP Matches This Click]].

## OTP Matches This Click

BOE OTP lasts five minutes and must belong to this Get-Code click. Match this
account's `extra.email`, IMAP UID above the pre-click watermark, ignore older mail.

Do not take "the latest mail in the folder". Snapshot max UID before clicking
获取验证码, then accept only `uid > watermark` and `To` = this login's CS mailbox.
Mail from before the click is leftover even if still inside five minutes. Another
account's new mail is rejected even if newer. If CAS shows no OTP after password,
the account is already verified today — succeed and do not read mail. Accounts
run serially so two Get-Code clicks do not overlap. See
[[service/app/domain/boe_srm_otp.py#pick_fresh_otp]].

## Database Hold Point

DDL and designs may be prepared; executing create/migrate/seed requires explicit
user authorization except where already recorded as authorized in project control.

Engine and Task share the conceptual product DB historically named
`nodeskclaw_task` with Engine schema `rpa_engine` in current test baselines;
production isolation targets remain documented in project control.
