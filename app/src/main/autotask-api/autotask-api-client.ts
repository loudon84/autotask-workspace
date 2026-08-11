import { getValidSession, refreshSession } from "@/main/auth/auth-client";
import { getEndpointConfig } from "@/main/auth/auth-endpoint-config-store";
import { buildAuthHeaders } from "@/main/auth/token-header-injector";
import { setMemorySession } from "@/main/auth/token-store";
import {
  type AutoTaskEndpointConfig,
  buildTaskUrl,
} from "@/types/endpoint-config";

export class AutotaskApiError extends Error {
  status: number;
  body?: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "AutotaskApiError";
    this.status = status;
    this.body = body;
  }
}

export interface AutotaskApiRequestInput {
  body?: unknown;
  method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
}

function buildUrl(
  config: AutoTaskEndpointConfig,
  path: string,
  query?: AutotaskApiRequestInput["query"]
): string {
  const url = new URL(buildTaskUrl(config, path));
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function doRequest<T>(
  input: AutotaskApiRequestInput,
  retried = false
): Promise<T> {
  const session = await getValidSession();
  if (!session) {
    throw new AutotaskApiError("未登录", 401);
  }

  const config = getEndpointConfig();
  const url = buildUrl(config, input.path, input.query);
  const headers = buildAuthHeaders(session);

  const res = await fetch(url, {
    method: input.method,
    headers,
    body: input.body === undefined ? undefined : JSON.stringify(input.body),
  });

  if (res.status === 401 && !retried) {
    const refreshed = await refreshSession();
    if (refreshed) {
      setMemorySession(refreshed);
      return doRequest<T>(input, true);
    }
    throw new AutotaskApiError("登录已过期", 401);
  }
  if (res.status === 403) {
    throw new AutotaskApiError("用户无权限!", 403);
  }

  if (!res.ok) {
    let message = `API request failed: ${res.status}`;
    let body: unknown;
    try {
      body = await res.json();
      const errBody = body as { detail?: string; message?: string };
      message = errBody.detail ?? errBody.message ?? message;
    } catch {
      // ignore
    }
    throw new AutotaskApiError(message, res.status, body);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export function requestAutotaskApi<T>(
  input: AutotaskApiRequestInput
): Promise<T> {
  return doRequest<T>(input);
}
