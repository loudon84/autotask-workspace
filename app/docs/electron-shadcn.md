# electron-shadcn Project Semantic Overview

## Purpose

`electron-shadcn` is an **opinionated Electron + React + Shadcn UI application scaffold**, not a library, framework, or reusable package. Its sole function is to pre-solve the hardest cross-cutting concerns of desktop app bootstrapping (IPC security boundary, custom title bar, theme sync, i18n persistence) so consumers can delete demo content and build on a working skeleton. The template is the product; the demo pages are disposable.

---

## Core Architecture

Three-process Electron model with a strict unidirectional trust boundary enforced at build time:

```
Main Process (Node.js / Electron)
  src/main.ts
    └─ createWindow()  →  BrowserWindow { contextIsolation: true, titleBarStyle: "hidden" }
    └─ registerListeners(mainWindow)  →  ipcMain.handle bindings

Preload Script (isolated bridge, no DOM, no full Node)
  src/preload.ts
    └─ exposeContexts()  →  contextBridge.exposeInMainWorld(...)

Renderer Process (React, zero Node access)
  src/renderer.ts  →  App.tsx
    └─ useEffect: syncThemeWithLocal() + updateAppLanguage()
    └─ RouterProvider  →  RootRoute  →  BaseLayout  →  <Outlet/>
         └─ pages/*
```

The preload is the **only** legal crossing point. `src/preload.ts` is intentionally three lines — its entire body is `exposeContexts()`. [1](#1-0) 

---

## Key Modules

`src/main.ts` — Electron entry. Owns `BrowserWindow` creation, listener registration, macOS lifecycle hooks. Nothing else belongs here. [2](#1-1) 

`src/helpers/ipc/` — The canonical IPC subsystem. Each capability is a self-contained subdirectory with three files:

| File | Side | Role |
|---|---|---|
| `*-channels.ts` | shared | string channel name constants |
| `*-listeners.ts` | main | `ipcMain.handle` registrations |
| `*-context.ts` | preload | `contextBridge.exposeInMainWorld` |

`listeners-register.ts` and `context-exposer.ts` are the **only aggregation points** — all new IPC features must register through them. [3](#1-2) [4](#1-3) 

`src/types.d.ts` — Single source of truth for the `window.*` API surface exposed to the renderer. Every new IPC context must declare its interface here. [5](#1-4) 

`src/routes/__root.tsx` + `src/routes/routes.tsx` — TanStack Router tree. `RootRoute` wraps every page in `BaseLayout`; `routes.tsx` is the only file to edit when adding pages. [6](#1-5) [7](#1-6) 

`src/layouts/BaseLayout.tsx` — Universal route shell. Composes `DragWindowRegion` (custom title bar) + `NavigationMenu` + `<main>` slot. Every route renders inside this. [8](#1-7) 

`src/helpers/theme_helpers.ts` — Dual-layer theme coordinator. Every theme mutation must call both `nativeTheme.themeSource` (via IPC) and `document.documentElement.classList` (CSS). `setTheme()` is the only correct write path. [9](#1-8) 

`src/localization/i18n.ts` + `src/helpers/language_helpers.ts` — i18n bootstrap with inline resource bundles. Persistence via `localStorage["lang"]`, hydrated at app init. [10](#1-9) 

`src/components/` — Three tiers:
- `ui/`: Shadcn-generated, treat as vendored, regenerate via CLI only
- `DragWindowRegion.tsx`, `ToggleTheme.tsx`, `LangToggle.tsx`: infrastructure components, not demo content
- `template/`: demo-only, safe to delete entirely for real projects

`forge.config.ts` — Packages for Windows (Squirrel), macOS (ZIP), Linux (RPM/DEB). Fuses lock the binary at package time. [11](#1-10) 

---

## Lifecycle

1. `app.whenReady()` → `createWindow()` → `BrowserWindow` with `titleBarStyle: "hidden"`, `contextIsolation: true`
2. `registerListeners(mainWindow)` — binds all `ipcMain.handle` channels before renderer loads
3. Preload executes → `exposeContexts()` → `window.themeMode` and `window.electronWindow` bridged into renderer
4. Renderer boots → `App.tsx` mounts under `React.StrictMode`
5. `useEffect` fires → `syncThemeWithLocal()` restores persisted theme; `updateAppLanguage(i18n)` restores persisted locale
6. `RouterProvider` mounts with `createMemoryHistory`, initial entry `/`
7. `RootRoute` renders `BaseLayout` → `<Outlet/>` resolves to the matched page component
8. macOS: `window-all-closed` skips quit on darwin; `activate` recreates window if none exist [12](#1-11) [13](#1-12) 

---

## Extension Points

**New native capability (IPC feature)**
Create `src/helpers/ipc/<feature>/` with `<feature>-channels.ts`, `<feature>-listeners.ts`, `<feature>-context.ts`. Register in `listeners-register.ts` and `context-exposer.ts`. Declare `window.<feature>` interface in `src/types.d.ts`. [14](#1-13) 

**New route/page**
Add component to `src/pages/`, import and `createRoute()` in `src/routes/routes.tsx`, append to `RootRoute.addChildren([...])`. The inline TODO comment in `routes.tsx` is the authoritative guide. [15](#1-14) 

**New language**
Add resource bundle to `src/localization/i18n.ts`; add `Language` entry to `src/localization/langs.ts` to surface it in `LangToggle`.

**New Shadcn component**
Run `npx shadcn@canary add <component>`; output lands in `src/components/ui/`. Do not hand-edit files in that directory.

**Theme token customization**
Modify CSS custom properties in `src/styles/global.css` under `:root` (light) and `.dark` (dark). These are the only values Shadcn components consume.

---

## Invariants — Do Not Violate

`contextIsolation: true` must remain. Any renderer access to Node APIs must go through a new IPC channel. Disabling isolation collapses the security model entirely. [16](#1-15) 

`createMemoryHistory` must stay. `createBrowserHistory` breaks under Electron's `file://` protocol. [17](#1-16) 

`DragWindowRegion` must remain in `BaseLayout` (or equivalent root shell). With `titleBarStyle: "hidden"`, removing it leaves no draggable region and no window controls. [18](#1-17) 

Theme state must stay in sync across both `nativeTheme.themeSource` (main process) and `document.documentElement.classList` (renderer). Updating only one side causes OS/visual mismatch. Always go through `setTheme()` or `toggleTheme()` in `theme_helpers.ts`. [19](#1-18) 

`react-compiler/react-compiler` ESLint rule is `"error"`. All components must be React Compiler-compliant; manual `useMemo`/`useCallback` anti-patterns will fail the lint step. [20](#1-19) 

Forge fuse `OnlyLoadAppFromAsar: true` and `RunAsNode: false` are set at package time. Do not introduce dynamic `require()` paths or external script loading that escapes the asar bundle. [21](#1-20) 

---

## Stable Abstractions vs. Volatile Details

**Stable — do not restructure**
- Three-file IPC pattern (`channels` / `listeners` / `context`) + their two aggregators
- `src/types.d.ts` as the sole `window.*` API contract
- `BaseLayout` as the universal route shell
- TanStack Router with memory history
- `setTheme()` / `toggleTheme()` as the only theme write paths

**Volatile — expected to change per project**
- `src/components/template/` — delete for real projects
- `src/localization/i18n.ts` inline bundles — placeholder; migrate to JSON files for production i18n
- `src/pages/` — all demo content
- CSS variable values in `src/styles/global.css` — defaults meant to be replaced
- `BrowserWindow` dimensions (800×600) and `BaseLayout` title string `"electron-shadcn"`

### Citations

**File:** src/preload.ts (L1-3)
```typescript
import exposeContexts from "./helpers/ipc/context-exposer";

exposeContexts();
```

**File:** src/main.ts (L13-37)
```typescript
function createWindow() {
  const preload = path.join(__dirname, "preload.js");
  const mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      devTools: inDevelopment,
      contextIsolation: true,
      nodeIntegration: true,
      nodeIntegrationInSubFrames: false,

      preload: preload,
    },
    titleBarStyle: "hidden",
  });
  registerListeners(mainWindow);

  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(
      path.join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`),
    );
  }
}
```

**File:** src/main.ts (L48-61)
```typescript
app.whenReady().then(createWindow).then(installExtensions);

//osX only
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
```

**File:** src/helpers/ipc/listeners-register.ts (L1-8)
```typescript
import { BrowserWindow } from "electron";
import { addThemeEventListeners } from "./theme/theme-listeners";
import { addWindowEventListeners } from "./window/window-listeners";

export default function registerListeners(mainWindow: BrowserWindow) {
  addWindowEventListeners(mainWindow);
  addThemeEventListeners();
}
```

**File:** src/helpers/ipc/context-exposer.ts (L1-7)
```typescript
import { exposeThemeContext } from "./theme/theme-context";
import { exposeWindowContext } from "./window/window-context";

export default function exposeContexts() {
  exposeWindowContext();
  exposeThemeContext();
}
```

**File:** src/types.d.ts (L7-24)
```typescript
// Preload types
interface ThemeModeContext {
  toggle: () => Promise<boolean>;
  dark: () => Promise<void>;
  light: () => Promise<void>;
  system: () => Promise<boolean>;
  current: () => Promise<"dark" | "light" | "system">;
}
interface ElectronWindow {
  minimize: () => Promise<void>;
  maximize: () => Promise<void>;
  close: () => Promise<void>;
}

declare interface Window {
  themeMode: ThemeModeContext;
  electronWindow: ElectronWindow;
}
```

**File:** src/routes/__root.tsx (L5-15)
```typescript
export const RootRoute = createRootRoute({
  component: Root,
});

function Root() {
  return (
    <BaseLayout>
      <Outlet />
    </BaseLayout>
  );
}
```

**File:** src/routes/routes.tsx (L6-23)
```typescript
// TODO: Steps to add a new route:
// 1. Create a new page component in the '../pages/' directory (e.g., NewPage.tsx)
// 2. Import the new page component at the top of this file
// 3. Define a new route for the page using createRoute()
// 4. Add the new route to the routeTree in RootRoute.addChildren([...])
// 5. Add a new Link in the navigation section of RootRoute if needed

// Example of adding a new route:
// 1. Create '../pages/NewPage.tsx'
// 2. Import: import NewPage from '../pages/NewPage';
// 3. Define route:
//    const NewRoute = createRoute({
//      getParentRoute: () => RootRoute,
//      path: '/new',
//      component: NewPage,
//    });
// 4. Add to routeTree: RootRoute.addChildren([HomeRoute, NewRoute, ...])
// 5. Add Link: <Link to="/new">New Page</Link>
```

**File:** src/routes/routes.tsx (L25-37)
```typescript
export const HomeRoute = createRoute({
  getParentRoute: () => RootRoute,
  path: "/",
  component: HomePage,
});

export const SecondPageRoute = createRoute({
  getParentRoute: () => RootRoute,
  path: "/second-page",
  component: SecondPage,
});

export const rootTree = RootRoute.addChildren([HomeRoute, SecondPageRoute]);
```

**File:** src/layouts/BaseLayout.tsx (L5-17)
```typescript
export default function BaseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <DragWindowRegion title="electron-shadcn" />
      <NavigationMenu />
      <main className="h-screen pb-20 p-2">{children}</main>
    </>
  );
}
```

**File:** src/helpers/theme_helpers.ts (L20-38)
```typescript
export async function setTheme(newTheme: ThemeMode) {
  switch (newTheme) {
    case "dark":
      await window.themeMode.dark();
      updateDocumentTheme(true);
      break;
    case "light":
      await window.themeMode.light();
      updateDocumentTheme(false);
      break;
    case "system": {
      const isDarkMode = await window.themeMode.system();
      updateDocumentTheme(isDarkMode);
      break;
    }
  }

  localStorage.setItem(THEME_KEY, newTheme);
}
```

**File:** src/helpers/theme_helpers.ts (L58-64)
```typescript
function updateDocumentTheme(isDarkMode: boolean) {
  if (!isDarkMode) {
    document.documentElement.classList.remove("dark");
  } else {
    document.documentElement.classList.add("dark");
  }
}
```

**File:** src/helpers/language_helpers.ts (L1-19)
```typescript
import type { i18n } from "i18next";

const languageLocalStorageKey = "lang";

export function setAppLanguage(lang: string, i18n: i18n) {
  localStorage.setItem(languageLocalStorageKey, lang);
  i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
}

export function updateAppLanguage(i18n: i18n) {
  const localLang = localStorage.getItem(languageLocalStorageKey);
  if (!localLang) {
    return;
  }

  i18n.changeLanguage(localLang);
  document.documentElement.lang = localLang;
}
```

**File:** forge.config.ts (L50-58)
```typescript
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
```

**File:** src/App.tsx (L10-19)
```typescript
export default function App() {
  const { i18n } = useTranslation();

  useEffect(() => {
    syncThemeWithLocal();
    updateAppLanguage(i18n);
  }, [i18n]);

  return <RouterProvider router={router} />;
}
```

**File:** src/helpers/ipc/theme/theme-context.ts (L9-17)
```typescript
export function exposeThemeContext() {
  const { contextBridge, ipcRenderer } = window.require("electron");
  contextBridge.exposeInMainWorld("themeMode", {
    current: () => ipcRenderer.invoke(THEME_MODE_CURRENT_CHANNEL),
    toggle: () => ipcRenderer.invoke(THEME_MODE_TOGGLE_CHANNEL),
    dark: () => ipcRenderer.invoke(THEME_MODE_DARK_CHANNEL),
    light: () => ipcRenderer.invoke(THEME_MODE_LIGHT_CHANNEL),
    system: () => ipcRenderer.invoke(THEME_MODE_SYSTEM_CHANNEL),
  });
```

**File:** src/routes/router.tsx (L10-13)
```typescript
const history = createMemoryHistory({
  initialEntries: ["/"],
});
export const router = createRouter({ routeTree: rootTree, history: history });
```

**File:** eslint.config.mjs (L23-25)
```javascript
    rules: {
      "react-compiler/react-compiler": "error",
    },
```
