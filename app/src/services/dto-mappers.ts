import type {
  PortalAccount,
  PortalCategory,
  PortalEntityType,
  PortalStatus,
} from "@/types/portal-account";
import type { ClientOpenMode } from "@/types/web-tab";

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}

export function mapKeysToCamel<T>(obj: unknown): T {
  if (obj === null || obj === undefined) {
    return obj as T;
  }
  if (Array.isArray(obj)) {
    return obj.map((item) => mapKeysToCamel(item)) as T;
  }
  if (typeof obj === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      const mappedKey = snakeToCamel(key);
      result[mappedKey] = key === "input" ? value : mapKeysToCamel(value);
    }
    return result as T;
  }
  return obj as T;
}

export interface ApiResponse<T> {
  code: number;
  data: T;
  errorCode?: number | null;
  message: string;
  messageKey?: string | null;
}

interface ApiEnvelope {
  code?: number;
  data?: unknown;
  error_code?: string | number | null;
  errorCode?: string | number | null;
  message?: string | null;
  message_key?: string | null;
  messageKey?: string | null;
}

function isApiEnvelope(data: unknown): data is ApiEnvelope {
  return (
    data !== null &&
    typeof data === "object" &&
    "data" in data &&
    ("code" in data || "message" in data || "error_code" in data)
  );
}

export function unwrapApiResponse<T>(response: ApiResponse<T>): T {
  if (response.code !== 0) {
    throw new Error(response.message || "请求失败");
  }
  return response.data;
}

function unwrapEnvelope(data: unknown): unknown {
  if (isApiEnvelope(data)) {
    const code = data.code ?? 0;
    if (code !== 0) {
      throw new Error(data.message ?? "请求失败");
    }
    return data.data;
  }

  return data;
}

export function mapListResponse<T>(data: unknown): T[] {
  const payload = unwrapEnvelope(data);

  if (Array.isArray(payload)) {
    return payload.map((item) => mapKeysToCamel<T>(item));
  }

  if (payload && typeof payload === "object") {
    const wrapped = payload as { items?: unknown[]; data?: unknown[] };
    const items = wrapped.items ?? wrapped.data ?? [];

    return Array.isArray(items)
      ? items.map((item) => mapKeysToCamel<T>(item))
      : [];
  }

  return [];
}

export function mapItemResponse<T>(data: unknown): T {
  return mapKeysToCamel<T>(unwrapEnvelope(data));
}

function normalizePortalStatus(status: unknown): PortalStatus {
  if (status === "ENABLED" || status === "enabled") {
    return "ENABLED";
  }
  if (status === "DISABLED" || status === "disabled") {
    return "DISABLED";
  }
  return "ENABLED";
}

function normalizeClientOpenMode(mode: unknown): ClientOpenMode {
  if (mode === "system_browser" || mode === "webcontents") {
    return mode;
  }
  return "webcontents";
}

function normalizeEntityType(type: unknown): PortalEntityType {
  if (type === "SUPPLIER" || type === "CUSTOMER") {
    return type;
  }
  return "CUSTOMER";
}

function normalizePortalCategory(value: unknown): PortalCategory {
  if (value === "BOE" || value === "TIANDI") {
    return value;
  }
  return "TIANDI";
}

export function mapPortalAccount(raw: unknown): PortalAccount {
  const data = mapKeysToCamel<Record<string, unknown>>(raw);

  return {
    id: String(data.id ?? ""),
    tenantId: String(data.tenantId ?? "default"),
    entityType: normalizeEntityType(data.entityType),
    erpEntityCode: String(
      data.erpEntityCode ?? data.customerCode ?? data.id ?? ""
    ),
    erpEntityName: String(data.erpEntityName ?? data.customerName ?? ""),
    businessEntity: String(data.businessEntity ?? ""),
    ou: String(data.ou ?? ""),
    category: normalizePortalCategory(data.category),
    portalName: String(data.portalName ?? data.name ?? ""),
    portalUrl: String(data.portalUrl ?? data.url ?? ""),
    loginAccount: String(data.loginAccount ?? ""),
    clientOpenMode: normalizeClientOpenMode(data.clientOpenMode),
    clientSessionPartition: String(data.clientSessionPartition ?? ""),
    status: normalizePortalStatus(data.status),
    ownerUserId: String(data.ownerUserId ?? data.createdBy ?? ""),
    ownerName: String(data.ownerName ?? ""),
    createdBy: String(data.createdBy ?? "system"),
    createdByName: String(data.createdByName ?? ""),
    createdAt: String(data.createdAt ?? ""),
    updatedAt: String(data.updatedAt ?? ""),
  };
}

export function mapPortalAccountList(data: unknown): PortalAccount[] {
  const payload = unwrapEnvelope(data);

  if (Array.isArray(payload)) {
    return payload.map((item) => mapPortalAccount(item));
  }

  if (payload && typeof payload === "object") {
    const wrapped = payload as { items?: unknown[]; data?: unknown[] };
    const items = wrapped.items ?? wrapped.data ?? [];

    return Array.isArray(items)
      ? items.map((item) => mapPortalAccount(item))
      : [];
  }

  return [];
}
