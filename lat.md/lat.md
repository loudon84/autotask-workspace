# AutoTask Workspace Knowledge Graph

Structured markdown for the AutoTask product workspace: architecture, ownership
boundaries, domain concepts, and design decisions across the five code roots.

Managed by [lat.md](https://www.npmjs.com/package/lat.md). Anchor source with
`@lat:` comments and `[[wiki links]]`. Detailed Engine internals also live in
`rpa-engine/lat.md/` (nested project graph).

## Sections

Index of workspace-level documentation.

- [[architecture]] — Five code roots, runtime topology, local Ubuntu bring-up, and execution path.
- [[domain]] — Shared product domain: portals, bindings, tasks, runs, processes, statements.
- [[design-decisions]] — Cross-cutting ownership and integration decisions.
- [[client]] — Electron Client (`app/`): Main/Renderer, IPC, and remote API facade.
- [[task-service]] — Task business API (`service/`): orchestration, lease, schedulers.
- [[rpa-engine]] — RPA Engine (`rpa-engine/`): registry, worker pool, Playwright runtime.
- [[flow-packages]] — Versioned Flow packages (`rpa-flows/`) and package contract.
- [[authoring]] — UiPath authoring sources (`rpa-authoring/`) as design prototypes.
- [[integration]] — Client ↔ Task ↔ Engine contracts and external systems.

## Primary Code Anchors

Key symbols carry `@lat:` comments that point back into this graph.

| Section | Symbol |
| --- | --- |
| [[client#Process Layers]] | [[app/src/ipc/router.ts#router]] |
| [[client#Data Access]] | [[app/src/services/autotask-api.ts#autotaskApi]] |
| [[design-decisions#Client Remote-By-Default With Main-Side HTTP]] | [[app/src/types/endpoint-config.ts#getApiMode]] |
| [[integration#Client ↔ Task]] | [[app/src/types/endpoint-config.ts#buildTaskUrl]] |
| [[integration#Client ↔ Engine]] | [[app/src/types/endpoint-config.ts#buildRpaEngineUrl]] |
| [[task-service]] | [[service/app/main.py#app]] |
| [[task-service#Orchestration]] | [[service/app/services/dispatch_service.py#lease_task]] |
| [[domain#AutomationTask]] | [[service/app/services/task_state_machine.py#TRANSITIONS]] |
| [[rpa-engine]] | [[rpa-engine/src/nodeskclaw_rpa_engine/api/app.py#create_app]] |
| [[flow-packages#Package Contract]] | [[rpa-flows/rpa_flow_login_demo/1.1.0/flow.py#run]] |
