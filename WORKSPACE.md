# AutoTask Product Workspace

This directory is the root workspace for AutoTask product development. Open this directory, rather than an individual repository, when starting a Codex session that may span Client, RPA Engine, Flow, UiPath, and product documentation work.

## Directory Map

| Directory | Responsibility | Source Control |
| --- | --- | --- |
| `app` | Electron Client（原 `AutoTask-studio` / `copilot-autotask`；package `name` 仍为 `AutoTask-studio`） | Existing Git repository |
| `service` | Task 业务 API（原 `nodeskclaw/nodeskclaw-task`；package `nodeskclaw-task`） | Existing project tree |
| `rpa-engine` | RPA Engine and Worker implementation | Existing nested Git repository |
| `rpa-flows` | Versioned Flow source packages and examples | Repository decision pending |
| `rpa-authoring\uipath` | UiPath authoring source used for translation/reference | Repository decision pending |
| `project-docs` | Product control, decisions, designs, and operations records | Documentation workspace |

## Working Rules

1. Read `project-docs\PROJECT_CONTROL.md` before project work.
2. Respect project ownership boundaries; do not mix Engine or Flow source into the Client repository.
3. Keep all text files UTF-8 and keep secrets out of source and development records.
4. Database preparation is allowed, but database execution remains blocked until explicitly authorized.
5. Use the old paths only as migration backups after the new workspace is accepted.

## Migration Baseline

- Client branch: `master`
- Client baseline HEAD: `17c87a75ffe93a9faa0d725fd79239e048b0b2fa`
- Client origin: `https://github.com/loudon84/copilot-autotask.git`
- Migration date: `2026-07-10`

