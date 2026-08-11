# shadcn-admin Project Semantic Overview

## Purpose

`shadcn-admin` is a **feature-complete admin panel template**, not a library or framework. It is a deployable React SPA that demonstrates production patterns for data-intensive dashboards. Its value is as a starting point to fork and extend — not to install as a dependency. It is explicitly **not** a backend, not a design system, and not a headless component library. [1](#0-0) 

---

## Core Architecture

**Runtime layer** (`src/main.tsx`): Single bootstrap file. Constructs `QueryClient` and `router` as module-level singletons, then mounts a fixed provider tree. Provider order is load-bearing: `QueryClientProvider → ThemeProvider → FontProvider → DirectionProvider → RouterProvider`. [2](#0-1) 

**Routing layer** (`src/routes/`, `src/routeTree.gen.ts`): TanStack Router with file-based routing. `routeTree.gen.ts` is **auto-generated** — never edit manually. The route tree has three top-level branches:
- `_authenticated/` — layout route enforcing auth, renders `AuthenticatedLayout`
- `(auth)/` — public auth pages (sign-in, sign-up, forgot-password, OTP)
- `(errors)/` — error boundary pages (404, 500, general)
- `clerk/` — optional Clerk-specific auth routes [3](#0-2) 

**Layout layer** (`src/components/layout/`): `AuthenticatedLayout` wraps all protected pages with `SearchProvider → LayoutProvider → SidebarProvider → AppSidebar + SidebarInset`. Sidebar behavior (collapsible mode, variant) is cookie-persisted via `LayoutProvider`. [4](#0-3) 

**Feature layer** (`src/features/`): Self-contained vertical slices. Each feature owns its `index.tsx` (page root), `components/` (feature-specific UI), and `data/` (mock data or API hooks). Features are **not** shared across each other.



---

## Key Modules

**`src/main.tsx`**: The only place `QueryClient` and `router` are instantiated. Global error routing (401 → `/sign-in`, 500 → `/500`) lives here in `queryCache.onError`. Mutation errors are globally handled via `handleServerError`. [5](#0-4) 

**`src/stores/auth-store.ts`**: Zustand store for mock auth. Persists `accessToken` to a cookie named `'thisisjustarandomstring'`. `auth.reset()` is the canonical logout action called by the global 401 handler. This is the **mock auth path** — Clerk integration lives in `src/routes/clerk/`. [6](#0-5) 

**`src/hooks/use-table-url-state.ts`**: The central abstraction for all data table state. Bridges TanStack Table's `ColumnFiltersState`/`PaginationState` to URL search params via TanStack Router's `navigate`. All table pages must use this hook to keep filter/pagination state shareable and bookmarkable. [7](#0-6) 

**`src/components/data-table/`**: Headless, reusable data table sub-components (`toolbar.tsx`, `pagination.tsx`, `faceted-filter.tsx`, `bulk-actions.tsx`, `column-header.tsx`, `view-options.tsx`). These are the stable primitives; feature-specific column definitions live inside each feature's `components/` directory.



**`src/components/layout/types.ts`**: Defines the `SidebarData` contract (`User`, `Team`, `NavGroup`, `NavItem`). Navigation structure is driven entirely by `src/components/layout/data/sidebar-data.ts` — this is the single file to edit when adding nav entries. [8](#0-7) 

**`src/context/`**: Five cookie-backed React contexts — `ThemeProvider`, `FontProvider`, `DirectionProvider`, `LayoutProvider`, `SearchProvider`. All persist user preferences to cookies (not `localStorage`) for SSR compatibility. These are stable infrastructure; do not add business logic here. [9](#0-8) [10](#0-9) 

**`src/lib/handle-server-error.ts`**: Canonical mutation error handler. Extracts `response.data.title` from Axios errors and fires a `sonner` toast. All `useMutation` calls inherit this via `QueryClient.defaultOptions.mutations.onError`. [11](#0-10) 

**`src/components/ui/`**: shadcn/ui components — Radix UI primitives wrapped with Tailwind. These are **copied source files**, not an npm dependency. Modifications here affect the entire app.

---

## Lifecycle

1. **Bootstrap** — `main.tsx` creates `QueryClient` (with global error handlers) and `router` (with `queryClient` in context), mounts provider tree
2. **Route resolution** — TanStack Router matches URL to generated `routeTree`, determines if `_authenticated` layout applies
3. **Auth gate** — `_authenticated` layout renders; if `accessToken` is absent, redirect to `/sign-in` (enforced at route `beforeLoad` or via 401 interception)
4. **Layout hydration** — `AuthenticatedLayout` reads cookies to restore sidebar state, theme, font, direction
5. **Feature render** — Feature `index.tsx` mounts its `Provider` (dialog/selection state via `useDialogState`), `Header`, `Main`, `Table`, `Dialogs`
6. **Data fetch** — TanStack Query fetches via Axios; errors bubble to `queryCache.onError` for global handling
7. **Table interaction** — `useTableUrlState` syncs filter/pagination to URL; browser back/forward works natively

---

## Extension Points

**Adding a new feature page**: Create `src/features/<name>/` with `index.tsx`, `components/`, `data/`. Add a route file at `src/routes/_authenticated/<name>/index.tsx`. Register the nav entry in `src/components/layout/data/sidebar-data.ts` using the `SidebarData` schema.

**Adding a new data table**: Compose from `src/components/data-table/` primitives. Use `useTableUrlState` for URL-synced state. Define columns in `features/<name>/components/<name>-columns.tsx`. Follow the `users` or `tasks` feature as the canonical pattern. [12](#0-11) 

**Swapping auth**: Replace `useAuthStore` usage with Clerk by switching to `src/routes/clerk/` routes. The `queryCache` 401 handler in `main.tsx` must be updated to call Clerk's sign-out instead of `useAuthStore.getState().auth.reset()`. [13](#0-12) 

**Adding a new theme color**: Extend `src/styles/theme.css` CSS variables using `oklch`. The `ThemeProvider` applies `light`/`dark` class to `<html>` — new tokens must be defined under both selectors.

**Adding a new sidebar variant or collapsible mode**: Extend the `Collapsible` / `Variant` union types in `src/context/layout-provider.tsx` and update `ConfigDrawer` UI options. [14](#0-13) 

---

## Invariants — Do Not Violate

**`routeTree.gen.ts` is generated.** Any manual edit is overwritten on next `vite dev` or `vite build`. Route shape is defined by file system structure under `src/routes/`.

**Provider order in `main.tsx` is fixed.** `RouterProvider` must be the innermost consumer because it depends on `QueryClient` via router context. Reordering breaks type-safe context injection.

**Cookie-based persistence is intentional.** All five context providers use cookies, not `localStorage`. Do not migrate to `localStorage` — this breaks SSR/hydration compatibility assumptions.

**`src/components/ui/` files are owned source.** They are not generated by shadcn CLI at runtime. Adding new shadcn components via CLI appends files here; modifying existing ones is safe but must be done deliberately.

**`useTableUrlState` is the only sanctioned table state mechanism.** Storing table filter/pagination in component state or Zustand breaks URL shareability, which is an explicit design goal. [15](#0-14) 

**Feature data is currently mocked.** `src/features/*/data/*.ts` files export static arrays. When connecting to a real API, replace these with TanStack Query `useQuery`/`useMutation` hooks — the table components accept `data` as a prop and are agnostic to the source. [16](#0-15) 

---

## What This System Is Not

- Not a micro-frontend — all features share one router, one query client, one bundle
- Not a monorepo — single `package.json`, single Vite build
- Not a component library — `src/components/ui/` is app-internal, not published
- Not API-connected by default — all data is static mock; no real backend contract exists yet
- Not multi-tenant by architecture — `TeamSwitcher` is UI-only with no routing or auth scope separation

### Citations

**File:** src/main.tsx (L1-19)
```typescript
import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { AxiosError } from 'axios'
import {
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { toast } from 'sonner'
import { useAuthStore } from '@/stores/auth-store'
import { handleServerError } from '@/lib/handle-server-error'
import { DirectionProvider } from './context/direction-provider'
import { FontProvider } from './context/font-provider'
import { ThemeProvider } from './context/theme-provider'
// Generated Routes
import { routeTree } from './routeTree.gen'
// Styles
import './styles/index.css'
```

**File:** src/main.tsx (L51-72)
```typescript
  queryCache: new QueryCache({
    onError: (error) => {
      if (error instanceof AxiosError) {
        if (error.response?.status === 401) {
          toast.error('Session expired!')
          useAuthStore.getState().auth.reset()
          const redirect = `${router.history.location.href}`
          router.navigate({ to: '/sign-in', search: { redirect } })
        }
        if (error.response?.status === 500) {
          toast.error('Internal Server Error!')
          // Only navigate to error page in production to avoid disrupting HMR in development
          if (import.meta.env.PROD) {
            router.navigate({ to: '/500' })
          }
        }
        if (error.response?.status === 403) {
          // router.navigate("/forbidden", { replace: true });
        }
      }
    },
  }),
```

**File:** src/main.tsx (L94-106)
```typescript
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <FontProvider>
            <DirectionProvider>
              <RouterProvider router={router} />
            </DirectionProvider>
          </FontProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </StrictMode>
  )
```

**File:** src/routes/_authenticated/route.tsx (L1-6)
```typescript
import { createFileRoute } from '@tanstack/react-router'
import { AuthenticatedLayout } from '@/components/layout/authenticated-layout'

export const Route = createFileRoute('/_authenticated')({
  component: AuthenticatedLayout,
})
```

**File:** src/components/layout/authenticated-layout.tsx (L14-41)
```typescript
export function AuthenticatedLayout({ children }: AuthenticatedLayoutProps) {
  const defaultOpen = getCookie('sidebar_state') !== 'false'
  return (
    <SearchProvider>
      <LayoutProvider>
        <SidebarProvider defaultOpen={defaultOpen}>
          <SkipToMain />
          <AppSidebar />
          <SidebarInset
            className={cn(
              // Set content container, so we can use container queries
              '@container/content',

              // If layout is fixed, set the height
              // to 100svh to prevent overflow
              'has-data-[layout=fixed]:h-svh',

              // If layout is fixed and sidebar is inset,
              // set the height to 100svh - spacing (total margins) to prevent overflow
              'peer-data-[variant=inset]:has-data-[layout=fixed]:h-[calc(100svh-(var(--spacing)*4))]'
            )}
          >
            {children ?? <Outlet />}
          </SidebarInset>
        </SidebarProvider>
      </LayoutProvider>
    </SearchProvider>
  )
```

**File:** src/stores/auth-store.ts (L24-52)
```typescript
export const useAuthStore = create<AuthState>()((set) => {
  const cookieState = getCookie(ACCESS_TOKEN)
  const initToken = cookieState ? JSON.parse(cookieState) : ''
  return {
    auth: {
      user: null,
      setUser: (user) =>
        set((state) => ({ ...state, auth: { ...state.auth, user } })),
      accessToken: initToken,
      setAccessToken: (accessToken) =>
        set((state) => {
          setCookie(ACCESS_TOKEN, JSON.stringify(accessToken))
          return { ...state, auth: { ...state.auth, accessToken } }
        }),
      resetAccessToken: () =>
        set((state) => {
          removeCookie(ACCESS_TOKEN)
          return { ...state, auth: { ...state.auth, accessToken: '' } }
        }),
      reset: () =>
        set((state) => {
          removeCookie(ACCESS_TOKEN)
          return {
            ...state,
            auth: { ...state.auth, user: null, accessToken: '' },
          }
        }),
    },
  }
```

**File:** src/hooks/use-table-url-state.ts (L10-16)
```typescript
export type NavigateFn = (opts: {
  search:
    | true
    | SearchRecord
    | ((prev: SearchRecord) => Partial<SearchRecord> | SearchRecord)
  replace?: boolean
}) => void
```

**File:** src/hooks/use-table-url-state.ts (L68-70)
```typescript
export function useTableUrlState(
  params: UseTableUrlStateParams
): UseTableUrlStateReturn {
```

**File:** src/components/layout/types.ts (L38-43)
```typescript
type SidebarData = {
  user: User
  teams: Team[]
  navGroups: NavGroup[]
}

```

**File:** src/context/theme-provider.tsx (L35-43)
```typescript
export function ThemeProvider({
  children,
  defaultTheme = DEFAULT_THEME,
  storageKey = THEME_COOKIE_NAME,
  ...props
}: ThemeProviderProps) {
  const [theme, _setTheme] = useState<Theme>(
    () => (getCookie(storageKey) as Theme) || defaultTheme
  )
```

**File:** src/context/layout-provider.tsx (L4-6)
```typescript
export type Collapsible = 'offcanvas' | 'icon' | 'none'
type Variant = 'inset' | 'sidebar' | 'floating'

```

**File:** src/context/layout-provider.tsx (L34-44)
```typescript
export function LayoutProvider({ children }: LayoutProviderProps) {
  const [collapsible, _setCollapsible] = useState<Collapsible>(() => {
    const saved = getCookie(LAYOUT_COLLAPSIBLE_COOKIE_NAME)
    return (saved as Collapsible) || DEFAULT_COLLAPSIBLE
  })

  const [variant, _setVariant] = useState<Variant>(() => {
    const saved = getCookie(LAYOUT_VARIANT_COOKIE_NAME)
    return (saved as Variant) || DEFAULT_VARIANT
  })

```

**File:** src/lib/handle-server-error.ts (L4-28)
```typescript
export function handleServerError(error: unknown) {
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.log(error)
  }

  let errMsg = 'Something went wrong!'

  if (
    error &&
    typeof error === 'object' &&
    'status' in error &&
    Number(error.status) === 204
  ) {
    errMsg = 'No content.'
  }

  if (error instanceof AxiosError) {
    const title = error.response?.data?.title
    if (typeof title === 'string' && title.length > 0) {
      errMsg = title
    }
  }

  toast.error(errMsg)
```

**File:** src/features/users/index.tsx (L12-12)
```typescript
import { users } from './data/users'
```

**File:** src/features/users/index.tsx (L16-44)
```typescript
export function Users() {
  const search = route.useSearch()
  const navigate = route.useNavigate()

  return (
    <UsersProvider>
      <Header fixed>
        <Search className='me-auto' />
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </Header>

      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex flex-wrap items-end justify-between gap-2'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>User List</h2>
            <p className='text-muted-foreground'>
              Manage your users and their roles here.
            </p>
          </div>
          <UsersPrimaryButtons />
        </div>
        <UsersTable data={users} search={search} navigate={navigate} />
      </Main>

      <UsersDialogs />
    </UsersProvider>
  )
```
