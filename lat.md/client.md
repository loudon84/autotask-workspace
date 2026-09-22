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

Product record: `project-docs/prd/AutoTask 在线更新.md`. SMC-Copilot uses the
same host under `/work/stable/`; AutoTask is `/autotask/stable/`.

### Check and install

The updater checks 15s after boot then every 6h; `autoDownload=false`. Only
Windows NSIS installs check; `npm start` does not.

- State machine: [[app/src/main/app-updater.ts#AppUpdater]]. User clicks 立即更新
  to download then install ([[app/src/main/app-updater.ts#AppUpdater#downloadAndInstall]]).
  Spawn `--updated --force-run`
  ([[app/src/main/delayed-setup-launch.ts#nsisUpdateStartCommand]]), then
  `app.quit()`. No `/S`. `--updated` skips the directory page and the running-app
  prompt. NSIS `customInit` relaunches via Explorer (`/autotask-detached`) so
  closing AutoTask cannot kill the setup. Copy or spawn failure does not quit.
  Never launch from AppData. Never `elevate.exe`. Logs:
  `<userData>/logs/updater.log`.
- Feed is baked into `resources/app-update.yml` by
  [[app/forge/maker-nsis-install-dir.ts#MakerNsisInstallDir]] and set at runtime.
  Override with `AUTOTASK_UPDATE_URL` (must stay under
  `https://release.superic.com/autotask/`). Artifact name carries the version.
  Shortcuts target `AutoTaskStudio.exe`; install dir stays
  `D:\Programs\SMC\AutoTask` (`allowToChangeInstallationDirectory: false`).
- `npm run release:build` refuses a dirty working tree (override
  `AUTOTASK_RELEASE_ALLOW_DIRTY=1` for debug only), then stages
  `app/release/autotask/<version>/` (exe, blockmap, `latest.yml`,
  `SHA256SUMS.txt` for all three, plus `release-manifest.json` schema
  `autotask.release.v1` carrying version/gitCommit/gitBranch/gitDirty/sha256 —
  Work's traceability manifest minus the signing fields, so any live build maps
  back to an exact commit). `release:publish`
  scps into `staging`, then server `app/scripts/server/promote-autotask-release.sh`
  moves to `releases/<version>` and flips `stable`. Ops uses `SMC_RELEASE_HOST` /
  `SMC_RELEASE_USER` / `SMC_RELEASE_ROOT=/data/smc-release` (product dir
  `autotask/`). Runtime and release read only `app/.env`. Git tracks blank
  `app/.env.example`. `.env.development` / `.env.production` are local backups
  and are not loaded. No Authenticode or publisher gate. Promote mirrors Work's
  `promote-work-release.sh` (same `PROMOTION_FAILED: CODE` errors, relative
  `stable` symlink, `mkdir -p releases`); the signing gate is replaced by
  artifact + SHA256SUMS + latest.yml sha512 + manifest version/gitCommit
  checks (`MANIFEST_VERSION_MISMATCH` / `MANIFEST_NO_GIT_COMMIT`).
  `releases/<version>` is
  immutable (`RELEASE_ALREADY_EXISTS`). Publishers use per-person SSH key auth;
  password logins get throttled (`Connection closed`). Installer publisher
  metadata is `SMC` via package.json `author` (`win.publisherName` is
  signing-cert matching only, do not set).

### Staging outside the install directory

NSIS replaces `D:\Programs\SMC\AutoTask`, so a running setup.exe must not live
under that folder.

Stage to `D:\Programs\SMC\updates\AutoTask`
([[app/src/main/pending-nsis-setup.ts#WINDOWS_SMC_UPDATES_DIR]]). Other desktop
apps use `updates\<product>`. If that folder is blocked, fall back to the SMC
root. After a successful launch, delete other `AutoTask-Studio-*-setup.exe`
files only ([[app/src/main/pending-nsis-setup.ts#removeStaleAutoTaskSetups]]).
Startup creates the updates folder
([[app/src/main/pending-nsis-setup.ts#ensureAutoTaskUpdatesDir]]).

### User-facing update UI

Dialogs stay short. Settings 「关于」shows the running version and 检查更新.

[[app/src/features/app-update/app-update-provider.tsx#AppUpdateProvider]]:
available 「是否立即更新？」; downloading 「请稍候。」; downloaded
「安装时将关闭 AutoTask。」 Settings default tab and the user menu open
[[app/src/features/settings/about-pane.tsx#AboutPane]]. Packaged builds only
can check; already-latest shows 「已是最新版本」. State pushes over
`APP_UPDATE_STATE_CHANGED` via preload.

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
