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
  `appUpdate`, `shell`, `webWorkspace`, `auth`, `autotaskApi`, `rpaEngine`).

Native embedded browsing uses WebContentsView (`web-workspace`) for portal
HumanAction work.

## Online Updates

Packaged Windows builds self-update from `https://release.superic.com/autotask/stable/`
via electron-updater (generic provider, no auth).

- Main-side state machine: [[app/src/main/app-updater.ts#AppUpdater]] — check
  15s after boot then every 6h; `autoDownload=false`, user confirms download
  and install. Dev / unpackaged / non-Windows never check.
- The feed URL is baked at build time by the NSIS maker's `publish` config
  ([[app/forge/maker-nsis-install-dir.ts#MakerNsisInstallDir]]); override with
  `AUTOTASK_UPDATE_URL`. Installer artifact name carries the version.
- Renderer dialogs live in `src/features/app-update/` (available → downloading
  → downloaded); state pushes over `APP_UPDATE_STATE_CHANGED` via preload.
- Release flow: `npm run release:build` (make + verify + stage), then the
  version folder is copied to the server by hand and promoted with
  `promote-autotask-release.sh` (no SSH from the build machine). Server-side
  scripts under `app/scripts/server/`.

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

Primary domains: tasks, processes, statements, workflows/bindings, SRM portals,
runs/artifacts, schedulers (independent timers: name/cron/enabled; see
[[app/src/features/schedulers/schedulers-list.tsx#SchedulersListPage]]),
web-workspace, and auth/endpoint configuration.
Shared business components live under `components/business/`; do not edit
generated `components/ui/`.

## Stack

Electron Forge + Vite, React 19, TanStack Router/Query, Tailwind 4, shadcn/ui,
oRPC + Zod, i18next, Vitest/Playwright.

Auth tokens and endpoint config persist in Main stores. Engine Flow upload IPC
exists; prefer Task Binding pins for day-to-day run configuration.
