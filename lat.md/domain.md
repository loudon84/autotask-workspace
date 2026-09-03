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

A ProcessInstance is a multi-stage business process (for example scan → SDMS
create → fill dates → sign → archive).

Sub-work is AutomationTasks linked by `process_instance_id`. Finish hooks advance
stages via Task process services.

## StatementBill

A StatementBill is the 天地伟业 statement head (check date/amount and related
stages: generate, invoice upload, submit review).

Like process instances, statement stages are driven by Task APIs and subordinate
AutomationTasks rather than by the Engine.

## SchedulerJob

A SchedulerJob is one cron schedule per Binding; Task’s JobScheduler fires tasks
when due.

Jobs are hot-reloaded; editing cron does not require a Task process restart.

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
