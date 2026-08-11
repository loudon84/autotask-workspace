import { ORPCError } from "@orpc/client";
import { ipc } from "@/ipc/manager";
import { unwrapApiResponse } from "@/types/api-response";

export interface AutotaskApiRequestInput {
  body?: unknown;
  method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
}

export class ApiClientError extends Error {
  status: number;
  body?: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.body = body;
  }
}

function normalizeQuery(
  query?: AutotaskApiRequestInput["query"]
): Record<string, string | number | boolean> | undefined {
  if (!query) {
    return;
  }
  const normalized: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) {
      normalized[key] = value;
    }
  }
  return Object.keys(normalized).length > 0 ? normalized : undefined;
}

function toApiClientError(err: unknown): ApiClientError {
  if (err instanceof ApiClientError) {
    return err;
  }

  if (err instanceof ORPCError && err.code === "AUTOTASK_API_ERROR") {
    const status =
      typeof err.status === "number" ? err.status : Number(err.status) || 500;
    return new ApiClientError(err.message, status, err.data);
  }

  const message = err instanceof Error ? err.message : "API 请求失败";
  return new ApiClientError(message, 500);
}

export async function requestAutotaskApi<T>(
  input: AutotaskApiRequestInput
): Promise<T> {
  try {
    const response = await ipc.client.autotaskApi.request({
      method: input.method,
      path: input.path,
      body: input.body,
      query: normalizeQuery(input.query),
    });
    return unwrapApiResponse<T>(response);
  } catch (err) {
    throw toApiClientError(err);
  }
}
