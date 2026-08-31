# Architecture

AutoTask is a multi-repo product workspace: an Electron Client, a Task business
API, an RPA Engine, versioned Flow packages, and UiPath authoring sources.

Product-wide control lives in `project-docs/`. Allowed code roots for agents are
only `app/`, `service/`, `rpa-engine/`, `rpa-flows/`, and `rpa-authoring/`. Do not
mix Engine or Flow source into the Client repository.

## Five Code Roots

Each root is an ownership boundary with its own tech stack and release cycle.

| Root | Role | Default port / form |
| --- | --- | --- |
| [[client|app/]] | AutoTask Studio desktop UI | Electron app |
| [[task-service|service/]] | Task orchestration API (`nodeskclaw-task`) | `4520` |
| [[rpa-engine|rpa-engine/]] | Flow Registry + Worker Pool + Runtime | `4610` |
| [[flow-packages|rpa-flows/]] | Versioned Playwright Flow packages | ZIP artifacts |
| [[authoring|rpa-authoring/]] | UiPath Studio prototypes | XAML projects |

Auth identity comes from an external NoDeskClaw backend (typically `:4510`). That
backend is **not** a code root in this workspace.

## Runtime Topology

At runtime the Client never talks to Flow source trees directly.

1. User authenticates via Auth backend; Client Main stores tokens.
2. Client Main calls Task under `/api/v1/autotask` with JWT.
3. Task owns portals, bindings, automation tasks, process/statement SOP, and
   schedules. It validates Flow pins against the Engine Registry.
4. Engine Worker Pool leases work from Task worker-api, loads an **exact**
   published Flow version, runs `flow.py:run(ctx)` in a MANAGED Playwright
   session, and finishes via Callback Outbox.
5. Client shows runs, artifacts, and human-in-the-loop workspace when Task enters
   `WAITING_HUMAN`.

Ubuntu bring-up for Task + Engine is orchestrated by workspace `dev.sh`
([[architecture#Local Ubuntu Bring-Up]]).

## Local Ubuntu Bring-Up

`dev.sh` is the Ubuntu-only one-shot installer/starter for Task (`service/`) and
Engine (`rpa-engine/`).

It resolves `PLAYWRIGHT_BROWSERS_PATH` (default
`/var/lib/nodeskclaw-rpa-engine/ms-playwright`), ensures the directory exists with
correct ownership, syncs both uv venvs, installs Chromium into that path when
missing, **stops any already-running workspace Task/Engine processes and frees
ports 4520/4610**, then starts both services and tails their logs. Re-running the
script is therefore safe: stale listeners are terminated before bind. Engine
startup exports the same browsers path so MANAGED Playwright sessions find
Chromium. Implementation: workspace root `dev.sh`.

## End-to-End Execution Path

A single RPA unit of work follows this path.

1. Operator (or [[task-service#Schedulers|scheduler]]) creates/submits an
   [[domain#AutomationTask|AutomationTask]] bound to a
   [[domain#WorkflowBinding|WorkflowBinding]].
2. Binding pins `rpaFlowId` + exact version/checksum validated by
   [[rpa-engine|Engine]].
3. Worker leases the task; Task snapshots portal credentials, input, and env
   integration bases into the lease command.
4. Engine resolves the published package (never “latest”), executes the Flow,
   records attempt state, and sends EVENT/FINISH callbacks.
5. Task updates run/task status; process/statement advancers or successor jobs
   may enqueue the next stage.

See [[integration]] for API contracts and [[design-decisions]] for why ownership
is split this way.
