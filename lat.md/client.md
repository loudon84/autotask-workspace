# Client

AutoTask Studio (`app/`) is the Electron + React desktop workbench for SRM
automation: tasks, processes, statements, portals, runs, and human-in-the-loop
browsing.

Package name remains `AutoTask-studio`. It talks to Auth, Task, and RPA Engine
over HTTP from the Main process only.

## Process Layers

Main, Preload, and Renderer stay isolated; Features call `actions/`, never raw
Node or `ipcRenderer`.

- Main entry: [[app/src/main.ts#createWindow]] boots the window and oRPC.
- Preload bridges MessagePort / tab events.
- Renderer boots via `src/renderer.ts` → `src/app.tsx` with TanStack Query.
- IPC surface is [[app/src/ipc/router.ts#router]] (`theme`, `window`, `app`,
  `shell`, `webWorkspace`, `auth`, `autotaskApi`, `rpaEngine`).

Native embedded browsing uses WebContentsView (`web-workspace`) for portal
HumanAction work.

## Data Access

Server data goes through the `autotaskApi` facade with mock|remote switching.

[[app/src/services/autotask-api.ts#autotaskApi]] selects implementation via
[[app/src/types/endpoint-config.ts#getApiMode]] (default `"remote"`). Remote
calls IPC into Main’s Task client. Endpoint builders:
[[app/src/types/endpoint-config.ts#buildTaskUrl]] and
[[app/src/types/endpoint-config.ts#buildRpaEngineUrl]].

Local/mock-oriented UI state may use Zustand; remote lists use TanStack Query
keys in `services/query-keys.ts`.

## Feature Modules

UI is feature-first under `src/features/` with thin TanStack file routes.

Primary domains: tasks, processes, statements, BOE invoice packing, workflows/bindings, SRM portals,
runs/artifacts, schedulers (Binding jobs plus tenant BOE match timer), web-workspace, and auth/endpoint configuration.
Shared business components live under `components/business/`; do not edit
generated `components/ui/`.

## Stack

Electron Forge + Vite, React 19, TanStack Router/Query, Tailwind 4, shadcn/ui,
oRPC + Zod, i18next, Vitest/Playwright.

Auth tokens and endpoint config persist in Main stores. Engine Flow upload IPC
exists; prefer Task Binding pins for day-to-day run configuration.
