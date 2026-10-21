# Domain

Shared AutoTask domain concepts span Client UI, Task persistence, and Engine
execution without duplicating ownership.

Task owns business state. Engine owns technical Flow versions and execution
attempts. Flows implement portal steps only through `ctx`.

## PortalAccount

A PortalAccount stores SRM/portal login metadata, ownership, ERP entity
hints, and a hardcoded customer category code used when leasing work.

Credentials are injected into the worker lease (and typically `ctx.credentials`).
ACL is ownership / managed-user / task-admin scoped on the Task service.
Category (`TIANDI` / `BOE`) is picked on the portal row; process menus bind to
that code. See [[design-decisions#Portal Category Is Hardcoded]].

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

A ProcessInstance is a multi-stage business process. New orders go from SDMS
create straight to 待回签; the user signs on the SRM page.

Sub-work is AutomationTasks linked by `process_instance_id`. Finish hooks advance
stages via Task process services.

### Manual SRM Sign

After SDMS create succeeds, the instance enters 待回签. Stage tabs and progress are 建单中, 待回签, then 已完成. 「去 SRM 签章」opens the portal order so a person fills 供方交期 and signs. Reply polling still waits for 已回签.

See [[service/app/services/process_instance_service.py#_handle_create_sdms_finished]] and [[app/src/features/processes/process-model.ts#srmOrderDetailUrl]].

### Delivery Dates Local Save

Official SRM has no separate save-date action; dates persist only with 签章. The date page and sign RPA remain in code, but those stages are off the tabs and progress bar.

AutoTask stores line dates locally as `WRITTEN` (no fill RPA). `request_sign`
always passes `order_lines`. Official sign Flow `1.1.5` fills 供方交期 in the
订单详情 pane (not the list tab's fixed 「详情」column) then clicks 签章.
Production Binding「天地伟业-芯云」has no `dryRun`; rehearsal keeps `dryRun: true`.
Demo portals keep sign `1.0.3` plus `temp_e2e_backfill_dates`. While a sign task
is `QUEUED`/`RUNNING`, Task rejects repeat `request_sign` and Client disables
「签章」. See
[[service/app/services/process_instance_service.py#submit_line_date]],
[[service/app/services/process_instance_service.py#request_sign]],
[[app/src/features/processes/process-model.ts#hasSignInFlight]], and
[[rpa-flows/rpa_flow_srm_sign_order/1.1.5/flow.py#run]].

## StatementBill

A StatementBill is the 天地伟业 statement head (check date/amount and related
stages: generate, invoice upload, submit review).

Like process instances, statement stages are driven by Task APIs and subordinate
AutomationTasks rather than by the Engine.

### Statement Amount Check

Generating a 天地伟业 statement compares SDMS `check_amount` to the selected receipt total with no tolerance.

A mismatch is a confirmable warning, not a hard stop. Client shows both amounts; after the user confirms, Task continues and records `amount_mismatch_confirmed` on the process summary. Missing SDMS bills still block. See [[service/app/services/statement_service.py#generate_statement]].

### Statement Generate Select All

Official generate 1.1.3 sets the receipt list to 100 rows per page, then clicks the header checkbox.

It checks 「共 N 条」against Client line count only. Totals at or below 100 stay on one page; totals above 100 click next and header-select each page. It does not tick rows or read 「已选择」. `dryRun` still locates 生成对账单 without clicking. See [[rpa-flows/rpa_flow_srm_stmt_generate/1.1.3/flow.py#ReceiptListAdapter#select_all_and_assert_count]].

## SchedulerJob

A SchedulerJob is an independent timer: name, enabled, cron, and an opaque
target. Task’s TimerScheduler notifies the registry when due.

The 调度中心 only maintains name/enabled/cron. What runs after notify is
registered by task code, not by Binding or portal. Jobs are hot-reloaded.
Each due fire is recorded in `timer_runs` (triggered/finished/status/error).
「立即执行」(`POST /timers/{id}/run`) bypasses enabled and cron entirely.
See [[service/app/models/timer.py#Timer]] and
[[service/app/services/timer_scheduler.py#TimerScheduler]].

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
