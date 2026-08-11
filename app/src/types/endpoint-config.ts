export interface AutoTaskEndpointConfig {
  aiosHomeUrl?: string;
  authBackendUrl: string;
  authPrefix: string;
  rpaEngineUrl: string;
  taskBackendUrl: string;
  taskPrefix: string;
}

export const defaultAutoTaskEndpointConfig: AutoTaskEndpointConfig = {
  authBackendUrl:
    import.meta.env.VITE_AUTOTASK_AUTH_BACKEND_URL ?? "http://127.0.0.1:4510",
  authPrefix: "/api/v1/auth",
  rpaEngineUrl:
    import.meta.env.VITE_AUTOTASK_RPA_ENGINE_URL ?? "http://127.0.0.1:4610",
  taskBackendUrl:
    import.meta.env.VITE_AUTOTASK_TASK_BACKEND_URL ?? "http://127.0.0.1:4520",
  taskPrefix: "/api/v1/autotask",
  aiosHomeUrl: "http://127.0.0.1:4517",
};

const TRAILING_SLASHES_PATTERN = /\/+$/;
const HTTP_SCHEME_PATTERN = /^https?:\/\//i;

function normalizeBaseUrl(value: string | undefined, fallback: string): string {
  const candidate = value?.trim().replace(TRAILING_SLASHES_PATTERN, "");
  if (!candidate) {
    return fallback;
  }
  if (!HTTP_SCHEME_PATTERN.test(candidate)) {
    return `http://${candidate}`;
  }
  return candidate;
}

export function normalizeAutoTaskEndpointConfig(
  config: Partial<AutoTaskEndpointConfig>
): AutoTaskEndpointConfig {
  const merged = { ...defaultAutoTaskEndpointConfig, ...config };
  return {
    ...merged,
    authBackendUrl: normalizeBaseUrl(
      merged.authBackendUrl,
      defaultAutoTaskEndpointConfig.authBackendUrl
    ),
    rpaEngineUrl: normalizeBaseUrl(
      merged.rpaEngineUrl,
      defaultAutoTaskEndpointConfig.rpaEngineUrl
    ),
    taskBackendUrl: normalizeBaseUrl(
      merged.taskBackendUrl,
      defaultAutoTaskEndpointConfig.taskBackendUrl
    ),
  };
}

export type ApiMode = "mock" | "remote";

export function getApiMode(): ApiMode {
  const mode = import.meta.env.VITE_AUTOTASK_API_MODE ?? "remote";
  return mode === "mock" ? "mock" : "remote";
}

export function buildAuthUrl(
  config: AutoTaskEndpointConfig,
  path: string
): string {
  const base = config.authBackendUrl.replace(TRAILING_SLASHES_PATTERN, "");
  const prefix = config.authPrefix.replace(TRAILING_SLASHES_PATTERN, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${prefix}${normalizedPath}`;
}

export function buildTaskUrl(
  config: AutoTaskEndpointConfig,
  path: string
): string {
  const base = config.taskBackendUrl.replace(TRAILING_SLASHES_PATTERN, "");
  const prefix = config.taskPrefix.replace(TRAILING_SLASHES_PATTERN, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${prefix}${normalizedPath}`;
}

export function buildRpaEngineUrl(
  config: AutoTaskEndpointConfig,
  path: string
): string {
  const base = config.rpaEngineUrl.replace(TRAILING_SLASHES_PATTERN, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}/api/v1${normalizedPath}`;
}
