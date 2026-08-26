import fs from "node:fs/promises";
import path from "node:path";
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

function formatApiErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") {
    return fallback;
  }
  const errBody = body as {
    detail?: unknown;
    message?: unknown;
    messageKey?: unknown;
  };
  if (typeof errBody.message === "string" && errBody.message.trim()) {
    return errBody.message;
  }
  if (typeof errBody.detail === "string" && errBody.detail.trim()) {
    return errBody.detail;
  }
  if (Array.isArray(errBody.detail) && errBody.detail.length > 0) {
    const parts = errBody.detail.map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object") {
        const row = item as { msg?: unknown; loc?: unknown };
        const loc = Array.isArray(row.loc)
          ? row.loc.filter((part) => part !== "body").join(".")
          : "";
        const msg = typeof row.msg === "string" ? row.msg : "";
        return [loc, msg].filter(Boolean).join(": ") || JSON.stringify(item);
      }
      return String(item);
    });
    return parts.join("; ") || fallback;
  }
  if (errBody.detail && typeof errBody.detail === "object") {
    try {
      return JSON.stringify(errBody.detail);
    } catch {
      return fallback;
    }
  }
  return fallback;
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
      message = formatApiErrorMessage(body, message);
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

export async function uploadStatementInvoiceFiles(input: {
  billId: string;
  filePaths: string[];
}): Promise<unknown> {
  return uploadInvoiceFiles(input, false);
}

async function uploadInvoiceFiles(
  input: { billId: string; filePaths: string[] },
  retried: boolean
): Promise<unknown> {
  const session = await getValidSession();
  if (!session) {
    throw new AutotaskApiError("未登录", 401);
  }

  const config = getEndpointConfig();
  const url = buildUrl(config, `/statements/${input.billId}/invoice`);
  const headers = { ...buildAuthHeaders(session) };
  delete headers["Content-Type"];

  const form = new FormData();
  for (const filePath of input.filePaths) {
    const bytes = await fs.readFile(filePath);
    form.append("files", new Blob([new Uint8Array(bytes)]), path.basename(filePath));
  }

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: form,
  });

  if (res.status === 401 && !retried) {
    const refreshed = await refreshSession();
    if (refreshed) {
      setMemorySession(refreshed);
      return uploadInvoiceFiles(input, true);
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
      message = formatApiErrorMessage(body, message);
    } catch {
      // ignore
    }
    throw new AutotaskApiError(message, res.status, body);
  }
  return (await res.json()) as unknown;
}
