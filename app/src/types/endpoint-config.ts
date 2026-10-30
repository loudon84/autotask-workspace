export interface AutoTaskEndpointConfig {
  aiosHomeUrl?: string;
  authBackendUrl: string;
  authPrefix: string;
  rpaEngineUrl: string;
  taskBackendUrl: string;
  taskPrefix: string;
}

const AUTH_BACKEND_URL = "http://192.168.102.247:4510";
const TASK_BACKEND_URL = "http://192.168.99.68:4520";
const ENGINE_BACKEND_URL = "http://192.168.99.68:4610";

export const defaultAutoTaskEndpointConfig: AutoTaskEndpointConfig = {
  authBackendUrl:
    import.meta.env.VITE_AUTOTASK_AUTH_BACKEND_URL ?? AUTH_BACKEND_URL,
  authPrefix: "/api/v1/auth",
  rpaEngineUrl:
    import.meta.env.VITE_AUTOTASK_RPA_ENGINE_URL ?? ENGINE_BACKEND_URL,
  taskBackendUrl:
    import.meta.env.VITE_AUTOTASK_TASK_BACKEND_URL ?? TASK_BACKEND_URL,
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

function preferNewServer(url: string): string {
  const bare = url.replace(TRAILING_SLASHES_PATTERN, "");
  if (bare === "http://127.0.0.1:4510" || bare === "http://localhost:4510") {
    return AUTH_BACKEND_URL;
  }
  if (bare === "http://127.0.0.1:4520" || bare === "http://localhost:4520") {
    return TASK_BACKEND_URL;
  }
  if (bare === "http://127.0.0.1:4610" || bare === "http://localhost:4610") {
    return ENGINE_BACKEND_URL;
  }
  return url;
}

export function normalizeAutoTaskEndpointConfig(
  config: Partial<AutoTaskEndpointConfig>
): AutoTaskEndpointConfig {
  const merged = { ...defaultAutoTaskEndpointConfig, ...config };
  return {
    authBackendUrl: preferNewServer(
      normalizeBaseUrl(
        merged.authBackendUrl,
        defaultAutoTaskEndpointConfig.authBackendUrl
      )
    ),
    authPrefix: merged.authPrefix,
    rpaEngineUrl: preferNewServer(
      normalizeBaseUrl(
        merged.rpaEngineUrl,
        defaultAutoTaskEndpointConfig.rpaEngineUrl
      )
    ),
    taskBackendUrl: preferNewServer(
      normalizeBaseUrl(
        merged.taskBackendUrl,
        defaultAutoTaskEndpointConfig.taskBackendUrl
      )
    ),
    taskPrefix: merged.taskPrefix,
    aiosHomeUrl: merged.aiosHomeUrl,
  };
}

export type ApiMode = "mock" | "remote";

// @lat: [[design-decisions#Client Remote-By-Default With Main-Side HTTP]]
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

// @lat: [[integration#Client ↔ Task]]
export function buildTaskUrl(
  config: AutoTaskEndpointConfig,
  path: string
): string {
  const base = config.taskBackendUrl.replace(TRAILING_SLASHES_PATTERN, "");
  const prefix = config.taskPrefix.replace(TRAILING_SLASHES_PATTERN, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${prefix}${normalizedPath}`;
}

// @lat: [[integration#Client ↔ Engine]]
export function buildRpaEngineUrl(
  config: AutoTaskEndpointConfig,
  path: string
): string {
  const base = config.rpaEngineUrl.replace(TRAILING_SLASHES_PATTERN, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}/api/v1${normalizedPath}`;
}

/** SDMS 销售订单查看页：fdId = headerId */
export function buildSdmsOmViewUrl(
  baseUrl: string | undefined,
  headerId: string
): string | null {
  const id = headerId.trim();
  if (!id) {
    return null;
  }
  const base = (baseUrl ?? "").trim().replace(TRAILING_SLASHES_PATTERN, "");
  if (!base) {
    return null;
  }
  return `${base}/sdms/om/sdms_om_main/sdmsOmMain.do?method=view&fdId=${encodeURIComponent(id)}`;
}

/** SDMS 客户对账单查看页：fdId = check_head_id */
export function buildSdmsCheckViewUrl(
  baseUrl: string | undefined,
  checkHeadId: string
): string | null {
  const id = checkHeadId.trim();
  if (!id) {
    return null;
  }
  const base = (baseUrl ?? "").trim().replace(TRAILING_SLASHES_PATTERN, "");
  if (!base) {
    return null;
  }
  return `${base}/sdms/check/sdms_check_cust_headers/sdmsCheckCustHeaders.do?method=view&fdId=${encodeURIComponent(id)}`;
}

/** SDMS 交货计划查看页：fdId = header_id。只打开查看，不打开编辑。 */
// @lat: [[integration#External Systems]]
export function buildSdmsDpViewUrl(
  baseUrl: string | undefined,
  headerId: string
): string | null {
  const id = headerId.trim();
  if (!id) {
    return null;
  }
  const base = (baseUrl ?? "").trim().replace(TRAILING_SLASHES_PATTERN, "");
  if (!base) {
    return null;
  }
  return `${base}/sdms/dp/sdms_dp_main/sdmsDpMain.do?method=viewDpInfo&fdId=${encodeURIComponent(id)}`;
}
