import { getValidSession } from "@/main/auth/auth-client";
import { getEndpointConfig } from "@/main/auth/auth-endpoint-config-store";
import { buildRpaEngineUrl } from "@/types/endpoint-config";
import type {
  FlowListResponse,
  FlowPackageUploadResponse,
  FlowScope,
  FlowValidation,
  FlowVersion,
} from "@/types/flow-registry";

export class RpaEngineApiError extends Error {
  body?: unknown;
  status: number;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "RpaEngineApiError";
    this.status = status;
    this.body = body;
  }
}

interface EngineErrorBody {
  error?: {
    code?: string;
    details?: unknown;
    message?: string;
  };
}

interface EngineRequest {
  body?: FormData | Record<string, unknown>;
  method?: "GET" | "POST";
  path: string;
  query?: Record<string, number | string | undefined>;
  scope: FlowScope;
}

function errorMessage(body: unknown, status: number): string {
  const parsed = body as EngineErrorBody;
  const message = parsed?.error?.message;
  const code = parsed?.error?.code;
  if (message && code) {
    return `${message}（${code}）`;
  }
  return message ?? `RPA Engine 请求失败：HTTP ${status}`;
}

async function actorHeaders(scope: FlowScope): Promise<Headers> {
  const session = await getValidSession();
  if (!session) {
    throw new RpaEngineApiError("未登录，无法访问 RPA Engine", 401);
  }

  const headers = new Headers({ "X-Actor-Id": session.user.id });
  if (scope === "TENANT") {
    const tenantId = session.organization?.id;
    if (!tenantId) {
      throw new RpaEngineApiError(
        "当前登录账号没有组织信息，不能管理租户私有 Flow",
        422
      );
    }
    headers.set("X-Tenant-Id", tenantId);
  }
  return headers;
}

async function requestEngine<T>({
  body,
  method = "GET",
  path,
  query,
  scope,
}: EngineRequest): Promise<T> {
  const config = getEndpointConfig();
  const url = new URL(buildRpaEngineUrl(config, path));
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) {
      url.searchParams.set(key, String(value));
    }
  }

  const headers = await actorHeaders(scope);
  let requestBody: BodyInit | undefined;
  if (body instanceof FormData) {
    requestBody = body;
  } else if (body !== undefined) {
    headers.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  const response = await fetch(url, {
    body: requestBody,
    headers,
    method,
  });
  if (!response.ok) {
    let parsed: unknown;
    try {
      parsed = await response.json();
    } catch {
      parsed = undefined;
    }
    throw new RpaEngineApiError(
      errorMessage(parsed, response.status),
      response.status,
      parsed
    );
  }
  return (await response.json()) as T;
}

export function listFlows(scope: FlowScope): Promise<FlowListResponse> {
  return requestEngine<FlowListResponse>({
    path: "/flows",
    query: { limit: 200, offset: 0, scope },
    scope,
  });
}

export function uploadFlowPackage(input: {
  content: Uint8Array;
  description?: string;
  fileName: string;
  labels?: string[];
  scope: FlowScope;
}): Promise<FlowPackageUploadResponse> {
  const form = new FormData();
  const content = new Uint8Array(input.content);
  form.set(
    "package",
    new Blob([content], { type: "application/zip" }),
    input.fileName
  );
  form.set("scope", input.scope);
  form.set("description", input.description?.trim() ?? "");
  form.set("labels", JSON.stringify(input.labels ?? []));
  return requestEngine<FlowPackageUploadResponse>({
    body: form,
    method: "POST",
    path: "/flows/packages",
    scope: input.scope,
  });
}

export function validateFlowVersion(input: {
  flowVersionId: string;
  scope: FlowScope;
}): Promise<FlowValidation> {
  return requestEngine<FlowValidation>({
    body: {},
    method: "POST",
    path: `/flow-versions/${input.flowVersionId}/validate`,
    scope: input.scope,
  });
}

export function publishFlowVersion(input: {
  flowVersionId: string;
  reason?: string;
  scope: FlowScope;
}): Promise<FlowVersion> {
  return requestEngine<FlowVersion>({
    body: { reason: input.reason?.trim() || null },
    method: "POST",
    path: `/flow-versions/${input.flowVersionId}/publish`,
    scope: input.scope,
  });
}
