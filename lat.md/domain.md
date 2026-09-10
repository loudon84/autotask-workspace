# Domain

Shared AutoTask domain concepts span Client UI, Task persistence, and Engine
execution without duplicating ownership.

Task owns business state. Engine owns technical Flow versions and execution
attempts. Flows implement portal steps only through `ctx`.

## PortalAccount

A PortalAccount stores SRM/portal login metadata, ownership, ERP entity
hints, and a hardcoded customer category code used when leasing work.

Credentials are injected into the worker lease (and typically `ctx.credentials`).
Operators can see the stored password on the portal edit form (masked by
default, one eye control to reveal). ACL is ownership / managed-user /
task-admin scoped on the Task service.
Category (`TIANDI` / `BOE`) is picked on the portal row; process menus bind to
that code. Category-specific fields live in JSONB `extra` (BOE CS mailbox is
`extra.email`); Client renders them from descriptors, not extra columns. Morning
SRM login unique-by `login_account` from those rows — do not hardcode AA/AD. See
[[design-decisions#Portal Category Is Hardcoded]],
[[design-decisions#Portal Extra Is JSONB]], and [[domain#MailInbox]].

## CategoryDocument

A CategoryDocument is a file (handbook, SOP note) owned by a hardcoded
category code, not by a single portal row.

Multiple 天地伟业 portals share one TIANDI document list. Files are stored on
the Task host under `ARTIFACT_LOCAL_DIR/category-docs`. See
[[design-decisions#Portal Category Is Hardcoded]].

## WorkflowTemplate

A WorkflowTemplate is a tenant-scoped recipe: code, input schema, and business
steps describing what kind of automation a Binding can offer.

Templates do not pin a Flow version. That pin lives on the Binding.

## WorkflowBinding

A WorkflowBinding joins portal × template × a **pinned published Flow** snapshot
(`rpaFlowId`, version, versionId, checksum) plus JSON `config`.

Binding config carries business knobs (`searches`, `dryRun`, sample PO numbers).
Integration host URLs and secrets stay in Task `.env`, not Binding JSON. See
[[design-decisions#Env-Level Integration Bases]].

## AutomationTask

An AutomationTask is one RPA work unit with a Task-owned state machine.

Typical path: `DRAFT → READY → QUEUED → LEASED → RUNNING → {WAITING_HUMAN|
SUCCESS|PARTIAL_SUCCESS|FAILED|CANCELLED}` (plus manual/human-operating variants).
Transitions are defined in Task
[[service/app/services/task_state_machine.py#TRANSITIONS]].

## RpaRun and Evidence

An RpaRun is Task’s business view of an execution: events, step runs, artifacts,
and optional [[domain#IntegrationCallLog|integration call logs]].

Engine separately records `rpa_execution_attempts` for technical attempts. Cross
IDs are string references, not foreign keys.

## HumanAction

A HumanAction is a first-class checkpoint while a task is `WAITING_HUMAN`
(captcha, MFA, or manual confirm).

The Client opens an embedded web workspace so an operator can finish the portal
step; Task then resumes or marks manual success.

## ProcessInstance

A ProcessInstance is a multi-stage business process (for example scan → SDMS
create → fill dates → sign → archive).

Sub-work is AutomationTasks linked by `process_instance_id`. Finish hooks advance
stages via Task process services.

## StatementBill

A StatementBill is the 天地伟业 statement head (check date/amount and related
stages: generate, invoice upload, submit review).

Like process instances, statement stages are driven by Task APIs and subordinate
AutomationTasks rather than by the Engine.

### Statement Amount Check

Generating a 天地伟业 statement compares SDMS `check_amount` to the selected receipt total with no tolerance.

A mismatch is a confirmable warning, not a hard stop. Client shows both amounts; after the user confirms, Task continues and records `amount_mismatch_confirmed` on the process summary. Missing SDMS bills still block. See [[service/app/services/statement_service.py#generate_statement]].

## BoeInvoicePacking

A BOE packing list is one process instance: match delivery plan, read WMS
packing list, RPA-enrich line items, save SRM draft, CS review, then submit as
a change-order vs JSON baseline.

v2.2 names stages from the CS point of view while keeping `BOE_PACK_*` status
codes stable. Matching is a tenant-level HTTP job (not a per-portal SRM scan);
leaf portals stay one-per-subcode. Cookie is keyed by SRM username (two logins
cover nine sites). Email OTP is a mail-inbox scene plus timer `boe.srm_login`,
not a CS daily SRM login; see [[domain#MailInbox]]. Qty mismatch is shown through save-draft but hard-blocks
only CS submit. Client header is a key-field subset, not the full SRM sample.
Line table shows 11 columns (PO and item frozen for horizontal scroll).
Enrich writes 行项目 / 订单数量 / 订单单位 / 剩余开票数 / 净重单位 from SRM.
CS review is a change-order vs `reviewBaseline`: the page lists diffs, submit
RPA applies only those diffs. Review also requires every editable header/line
field and a manual attachment table: 箱单 filename contains `pl` (any case;
`PL-{invoice}.pdf` is only a convention), 发票=`{invoice}.pdf`,
提运单 any PDF, 双签 one file per unique PO named `{po}.pdf`. 箱单/发票/提运单
match SRM default rows (delete disabled) so the Client hides delete for them;
only 双签 can be added or removed. Submit Binding uses
`dryRun: true` (fail-closed if missing): Flow uploads attachments and
saves the draft, then stops — it never clicks 提交. Draft:
`project-docs/prd/boe/AutoTask-BOE v1.0 设计-发票箱单SOP.md`.

Phase 1 code lives in Task [[service/app/domain/boe_packing.py#PROCESS_CODE]], Client
route `/process-instances/invoice-packing`, and Flows `rpa_flow_srm_boe_pack_*`.
WMS is `SMC_API_BASE_URL` + `/aiats/wms_sjh_pl_boe` with param `erpno`
(delivery-plan number) and a flat line array
(`cuspo`/`cusitem`/`qty`/`netweight`/`cubic`/`coo`); header volume is the sum
of line `cubic` (verified 2026-09-08). Net weight and volume keep at most five
decimal places with trailing zeros stripped. `doc_no` now returns `[]`; do not use it.
Region maps are a wide table
(see [[design-decisions#Region Map Wide Table]]): one row per region code with
`default_name` plus per-SRM columns (`boe_name`, empty = fall back to default).
Alembic `b2d4f6a81935` migrated on the test DB
2026-09-07 (production not yet); same-login BOE RPA is serialized when leasing. When the
region-map table is missing, `list_maps` answers empty via a SAVEPOINT
(`db.begin_nested()`) — it must never `db.rollback()` the shared session, or it
silently discards the caller's pending work (e.g. the just-created match
instance), which once surfaced as "Instance is not persistent within this
Session" on the post-commit `db.refresh()`. Unmapped WMS `coo` stays on
`BOE_PACK_FETCH_WMS` (`BOE_WMS_REGION_UNMAPPED`); CS maintains the map and
retries — enrich does not start
([[service/app/domain/boe_packing.py#unmapped_region_codes]]). Missing net-weight unit defaults to 千克.
Retry is shown only after lastError or a FAILED task, never while RPA is
in flight. List 流水号 links to detail or shows `—`. Process-instance
sub-tasks open a task drawer instead of leaving the page.
The match timer is the independent
timer `boe.pack_match` (see [[domain#SchedulerJob]]), maintained on 调度中心 like
any other timer; it stays off until an operator enables it.
List and detail put 发票箱单流水号 first (empty until save-draft). Delivery-plan
`header_id` is stored as `headerId` so Client can open SDMS `viewDpInfo`; the
packing form stays the edit surface and does not hold that id.
Packing RPA enqueue is per-portal Binding. A missing enrich Binding used to
skip the task with no instance error; it now records `PROCESS_BINDING_MISSING`
so the list shows why there is no task. Demo portal C000142-01 was bound first;
the other BOE portals were bound 2026-09-09.

List and detail show SOP 阶段 plus 运行状态 (in-flight RPA vs failed vs
waiting for CS), matching customer-order list/detail.

Matching skips an **open** instance with the same portal+交货计划号.
Cancelled rows do not occupy the unique key, so the next timer tick (or 立即匹配)
INSERTs a new instance. The timer does not interpret 作废. See
[[design-decisions#Open Process Instance Unique Key]] and
[[domain#BoePackCancelPaths]].

## BoePackCancelPaths

CS 作废 is local-only when there is no SRM draft number; with a draft, RPA must
search/delete it first and only then flip the instance to CANCELLED.

Discriminator is `summary.srmDraftNo`. Empty → 2.1: status CANCELLED immediately
([[service/app/services/boe_packing_service.py#cancel_instance]]). Present →
stage `BOE_PACK_DELETING_DRAFT` while still ACTIVE, enqueue
`srm_boe_pack_delete_draft`; local cancel happens in `dispatch_finished` after
SUCCESS (deleted or `alreadyMissing`). Inflight enrich/save/submit blocks
cancel. Binding must exist on BOE portals or 2.2 cannot run. After delete,
RPA clicks list 「搜 索」 then waits for 「暂无数据」 (1.0.1).

Retry of `BOE_PACK_DELETING_DRAFT` re-enqueues the same Flow. Every run searches
first: 「暂无数据」 is `alreadyMissing` SUCCESS, then Task CANCELLED locally. It
must not click 删除 again when SRM already removed the draft. A previous
`BOE_DRAFT_STILL_PRESENT` does not skip that search.

## SchedulerJob

A SchedulerJob is an independent timer: name, enabled, cron, and an opaque
target. Task’s TimerScheduler notifies the registry when due.


Jobs are hot-reloaded; editing cron does not require a Task process restart.
Tenant-level jobs that are not per-portal (BOE match delivery plan
`boe.pack_match`, BOE SRM morning login `boe.srm_login`) are registered as
ordinary timers too — one row per job, not per portal.

The 调度中心 only maintains name/enabled/cron. Cron is China wall time
(`Asia/Shanghai`), not the Task host timezone. What runs after notify is
registered by task code, not by Binding or portal. Jobs are hot-reloaded.
Due fire is computed by APScheduler `CronTrigger`; stored cron is crontab
5-field with dow `0`/`7`=Sunday, shimmed before use
([[design-decisions#Due Time Uses APScheduler]]). A fire within 2 minutes of
its slot still counts as that slot; missed slots are not replayed.
Each due fire is recorded in `timer_runs` (triggered/finished/status/error).
「立即执行」(`POST /timers/{id}/run`) bypasses enabled and cron entirely.
See [[service/app/models/timer.py#Timer]] and
[[service/app/services/timer_scheduler.py#TimerScheduler]].


## MailInbox

Task owns a generic mail inbox (IMAP first) so later scenes can create sales
orders from mail; BOE SRM OTP is only scene 1.

The IMAP account is a system mailbox. Login targets come from enabled BOE
portal rows: unique `login_account`, mailbox from `extra.email` (CS address).
OTP matching is this-click only: `To` plus IMAP UID watermark plus 5-minute
TTL; leftover folder mail is never reused. If CAS has no OTP after password,
login succeeds without reading mail. A bounce back to the login page is one
failed attempt; the same 5-minute code is reused for two more logins.
Timer `boe.srm_login` (default 07:00, off)
probes IMAP then dispatches thin Flow `srm_boe_login` serially; run summaries
land in `timer_runs` without OTP digits. Daytime packing Flows share
[[rpa-engine/src/nodeskclaw_rpa_engine/runtime/boe_srm.py#login_boe_srm]].
IMAP connector: [[service/app/integrations/imap_mail.py#ImapMailConnector]].
Picker: [[service/app/domain/boe_srm_otp.py#pick_fresh_otp]]. Design:
`project-docs/prd/boe/AutoTask-BOE 邮件读取.md`.
Thin login Flow `rpa_flow_srm_boe_login` 1.0.0 is published by
[[rpa-engine/scripts/_publish_boe_login.py#main]] and bound on enabled BOE
portals by [[service/scripts/boe/bind_boe_login.py#main]] (not the packing
bind script).

## Flow Package

A Flow Package is a versioned ZIP (`manifest.json`, `selectors.json`, `flow.py`)
stored in object storage and cached on workers.

Entry contract is `flow.py:run(ctx)`. Flows must not start browsers, attach CDP,
or touch business databases. See [[flow-packages]].

## IntegrationCallLog

An IntegrationCallLog stores worker-reported outbound HTTP calls (URL, request,
response) with redaction for ops diagnosis.

Task surfaces these on failed-task detail without changing the primary task
error message contract.
